"""
API Routes Package
Contains Flask blueprint for device registration.
"""

from src.application.routes.device_routes import device_api

__all__ = [
    "device_api",
]
