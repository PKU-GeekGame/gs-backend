from flask import Flask, redirect, request
from sqlalchemy import select
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_admin import Admin
from typing import Any, Optional
from functools import wraps

from .views import StatusView, VIEWS_MODEL, VIEWS_FILE
from .. import secret
from .. import store
from .. import utils

app = Flask(__name__, static_url_path=f'{secret.ADMIN_URL}/static')

app.config['DEBUG'] = False
app.config['ADMIN_URL'] = secret.ADMIN_URL
app.config['SQLALCHEMY_DATABASE_URI'] = secret.DB_CONNECTOR
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_size': 2,
    'pool_use_lifo': True,
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = secret.ADMIN_SESSION_SECRET

@app.template_filter('timestamp_s')
def timestamp_s_filter(timestamp_s: float) -> str:
    return utils.format_timestamp(timestamp_s)

@app.template_filter('timestamp_ms')
def timestamp_ms_filter(timestamp_ms: float) -> str:
    return utils.format_timestamp(timestamp_ms/1000)

@app.template_filter('size')
def size_filter(size: int) -> str:
    return utils.format_size(size)

db = SQLAlchemy(app, model_class=store.SqlBase)
migrate = Migrate(app, db)

def secured(cls: Any) -> Any:
    # noinspection PyMethodMayBeStatic
    @wraps(cls, updated=())
    class SecuredView(cls): # type: ignore
        def is_accessible(self) -> bool:
            auth_token = request.cookies.get('auth_token', None)
            if not auth_token:
                return False

            user: Optional[store.UserStore] = db.session.execute(select(store.UserStore).where(store.UserStore.auth_token==auth_token)).scalar()

            if user is None:
                return False

            if not secret.IS_ADMIN(user):
                return False

            if not secret.IS_DESTRUCTIVE_ADMIN(user) and not getattr(self, 'IS_SAFE', False):
                return False

            return True

        # noinspection PyUnusedLocal
        def inaccessible_callback(self, name: str, **kwargs: Any) -> Any:
            return redirect('/')

    return SecuredView

def remove_suffix(s: str, suffix: str) -> str:
    if s.endswith(suffix):
        return s[:-len(suffix)]
    else:
        return s

admin = Admin(
    app,
    index_view=secured(StatusView)(name='Status', url=f'{secret.ADMIN_URL}/admin'),
    url=f'{secret.ADMIN_URL}/admin',
    template_mode='bootstrap3',
    base_template='base.html',
)

for model_name, view in VIEWS_MODEL.items():
    friendly_name = remove_suffix(model_name, 'Store')
    admin.add_view(secured(view)(
        getattr(store, model_name), db.session, name=friendly_name, endpoint=friendly_name.lower(), category='Models',
    ))

for friendly_name, (view, path) in VIEWS_FILE.items():
    admin.add_view(secured(view)(
        path, name=friendly_name, endpoint=friendly_name.lower(), category='Files',
    ))

@app.route(f'{secret.ADMIN_URL}/')
def index() -> Any:
    return redirect(f'{secret.ADMIN_URL}/admin')
