from .api import blueprint as api_blueprint

def register(app):
    app.register_blueprint(api_blueprint)
