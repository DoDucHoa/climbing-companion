# Import blueprints from routes package
from src.application.routes import (
    dt_api,
    dr_api,
    dt_management_api,
    emergency_contact_api,
)


def register_api_blueprints(app):
    app.register_blueprint(dt_api)
    app.register_blueprint(dr_api)
    app.register_blueprint(dt_management_api)
    app.register_blueprint(emergency_contact_api)
