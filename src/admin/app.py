from flask import Flask, redirect, request
from sqlalchemy import select
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_admin import Admin, AdminIndexView
from flask_admin.form import SecureForm
from flask_admin.contrib.sqla import ModelView
from typing import Any, Optional
from functools import wraps

from .views import StatusView, VIEWS, TemplateView, WriteupView, FilesView
from .. import secret
from .. import store

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

            user: Optional[store.UserStore] = \
                db.session.execute(select(store.UserStore).where(store.UserStore.auth_token==auth_token)).scalar()
            if user is None or not secret.IS_ADMIN(user):
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

for model_name in dir(store):
    if model_name.endswith('Store'):
        print('- added model:', model_name)
        admin.add_view(secured(VIEWS.get(model_name, ModelView))(
            getattr(store, model_name), db.session, name=remove_suffix(model_name, 'Store'), category='Models',
        ))

admin.add_view(secured(TemplateView)(secret.TEMPLATE_PATH, name='Template', category='Files'))
admin.add_view(secured(WriteupView)(secret.WRITEUP_PATH, name='Writeup', category='Files'))
admin.add_view(secured(FilesView)(secret.MEDIA_PATH, name='Media', endpoint='media', category='Files'))
admin.add_view(secured(FilesView)(secret.ATTACHMENT_PATH, name='Attachment', endpoint='attachment', category='Files'))

@app.route(f'{secret.ADMIN_URL}/')
def index() -> Any:
    return redirect(f'{secret.ADMIN_URL}/admin')
