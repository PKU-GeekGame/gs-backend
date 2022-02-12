from flask import Flask, redirect, url_for, request
from sqlalchemy import select
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # type: ignore
from flask_admin import Admin, AdminIndexView # type: ignore
from flask_admin.form import SecureForm # type: ignore
from flask_admin.contrib.sqla import ModelView # type: ignore
from typing import Any, Optional

from .views import VIEWS
from .. import secret
from .. import store

app = Flask(__name__, static_url_path=f'{secret.ADMIN_URL}/static')

app.config['ADMIN_URL'] = secret.ADMIN_URL
app.config['SQLALCHEMY_DATABASE_URI'] = secret.DB_CONNECTOR
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = secret.ADMIN_SESSION_SECRET
db = SQLAlchemy(app, model_class=store.SqlBase)
migrate = Migrate(app, db)

def secured(cls): # type: ignore
    class SecuredView(cls):
        def is_accessible(self) -> bool:
            auth_token = request.cookies.get('auth_token', None)
            if not auth_token:
                return False

            user: Optional[store.UserStore] = \
                db.session.execute(select(store.UserStore).where(store.UserStore.auth_token==auth_token)).scalar()
            if user is None or user.group not in secret.ADMIN_GROUPS or user.id not in secret.ADMIN_UIDS:
                return False

            return True

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
    index_view=secured(AdminIndexView)(url=f'{secret.ADMIN_URL}/admin'),
    url=f'{secret.ADMIN_URL}/admin',
    template_mode='bootstrap3'
)
for model_name in dir(store):
    if model_name.endswith('Store'):
        print('- added model:', model_name)
        admin.add_view(secured(VIEWS.get(model_name, ModelView))(
            getattr(store, model_name), db.session, name=remove_suffix(model_name, 'Store')
        ))

@app.route(f'{secret.ADMIN_URL}')
def index() -> Any:
    return redirect(f'{secret.ADMIN_URL}/admin')
