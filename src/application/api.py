# Import blueprints from routes package
from src.application.routes import device_api


def register_api_blueprints(app):
    app.register_blueprint(device_api)
