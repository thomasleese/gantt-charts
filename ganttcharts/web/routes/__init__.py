from .api import blueprint as api_blueprint
from .frontend import blueprint as frontend_blueprint


def register(app):
    app.register_blueprint(api_blueprint)
    app.register_blueprint(frontend_blueprint)
