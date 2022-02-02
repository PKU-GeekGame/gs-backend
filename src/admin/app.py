from flask import Flask, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView

from .. import secret
from .. import store

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = secret.DB_CONNECTOR
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = secret.ADMIN_SECRET
db = SQLAlchemy(app, model_class=store.Base)
migrate = Migrate(app, db)

class AuthedAdminIndexView(AdminIndexView):
    def is_accessible(self):
        admin_token = request.cookies.get('admin_token', None)
        if not admin_token:
            return False

        stmt = db.select(store.UserStore).where(store.UserStore.admin_token_or_null==admin_token)
        user: store.UserStore = db.session.execute(stmt).scalar_one_or_none()
        if not user:
            return False
        if not user.enabled:
            return False

        return True

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth'))

def remove_suffix(s, suffix):
    if s.endswith(suffix):
        return s[:-len(suffix)]

admin = Admin(app, endpoint='admin', index_view=AuthedAdminIndexView(), url='/admin', template_mode='bootstrap3')
for model_name in dir(store):
    if model_name.endswith('Store'):
        print('- added model:', model_name)
        admin.add_view(ModelView(getattr(store, model_name), db.session, name=remove_suffix(model_name, 'Store')))

@app.route('/')
def auth():
    return 'hello?'

if __name__ == '__main__':
    app.run()