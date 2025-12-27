"""
API Routes Package
Contains all Flask blueprint definitions organized by domain.
"""

from src.application.routes.dt_routes import dt_api
from src.application.routes.dr_routes import dr_api
from src.application.routes.dt_management_routes import dt_management_api
from src.application.routes.emergency_contact_routes import emergency_contact_api
from src.application.routes.device_routes import device_api

__all__ = [
    "dt_api",
    "dr_api",
    "dt_management_api",
    "emergency_contact_api",
    "device_api",
]
