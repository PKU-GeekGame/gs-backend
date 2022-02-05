from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # type: ignore
from flask_admin import Admin, AdminIndexView # type: ignore
from flask_admin.contrib.sqla import ModelView # type: ignore
from typing import Any

from .. import secret
from .. import store

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = secret.DB_CONNECTOR
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = secret.ADMIN_SESSION_SECRET
db = SQLAlchemy(app, model_class=store.SqlBase)
migrate = Migrate(app, db)

class AuthedAdminIndexView(AdminIndexView): # type: ignore
    def is_accessible(self) -> bool:
        return True # todo: add real auth

    def inaccessible_callback(self, name: str, **kwargs: Any) -> Any:
        return redirect(url_for('auth'))

def remove_suffix(s: str, suffix: str) -> str:
    if s.endswith(suffix):
        return s[:-len(suffix)]
    else:
        return s

admin = Admin(app, endpoint='admin', index_view=AuthedAdminIndexView(), url='/admin', template_mode='bootstrap3')
for model_name in dir(store):
    if model_name.endswith('Store'):
        print('- added model:', model_name)
        admin.add_view(ModelView(getattr(store, model_name), db.session, name=remove_suffix(model_name, 'Store')))

@app.route('/')
def auth() -> str:
    return 'hello?'

if __name__ == '__main__':
    app.run()