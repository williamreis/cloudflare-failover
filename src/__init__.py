import os
from flask import Flask
from .views import main, auth, domain, log


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
    app.template_folder = 'templates'
    app.static_folder = 'static'
    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(domain)
    app.register_blueprint(log)

    return app
