from flask import Flask
from flask_cors import CORS
from src.virtualization.digital_replica.schema_registry import SchemaRegistry
from src.virtualization.digital_replica.dr_factory import DRFactory
from src.services.database_service import DatabaseService
from src.digital_twin.dt_factory import DTFactory
from src.services.mqtt_service import MQTTService
from src.services.telegram_service import TelegramService
from src.application.api import register_api_blueprints
from src.application.auth_routes import auth_bp
from config.config_loader import ConfigLoader
import os
import logging
from werkzeug.serving import is_running_from_reloader

# Configure logging only once (not in reloader parent process)
if not is_running_from_reloader():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


class FlaskServer:
    def __init__(self):
        self.app = Flask(__name__, template_folder="templates", static_folder="static")
        self.app.secret_key = os.urandom(24)
        CORS(self.app)
        self._init_components()
        self._register_blueprints()
        self._init_mqtt()

    def _init_components(self):
        """Initialize all required components and store them in app config"""
        schema_registry = SchemaRegistry()

        # Load schemas
        schema_registry.load_schema(
            "emergency_contact", "config/emergency_contact_schema.yaml"
        )
        schema_registry.load_schema("user", "config/user_schema.yaml")
        schema_registry.load_schema("device", "config/device_schema.yaml")
        schema_registry.load_schema(
            "device_pairing", "config/device_pairing_schema.yaml"
        )
        schema_registry.load_schema(
            "climbing_session", "config/climbing_session_schema.yaml"
        )
        schema_registry.load_schema("session_event", "config/session_event_schema.yaml")

        # Load database configuration
        db_config = ConfigLoader.load_database_config()
        connection_string = ConfigLoader.build_connection_string(db_config)

        # Initialize DatabaseService with populated schema_registry
        db_service = DatabaseService(
            connection_string=connection_string,
            db_name=db_config["settings"]["name"],
            schema_registry=schema_registry,
        )
        db_service.connect()

        # Initialize DTFactory
        dt_factory = DTFactory(db_service, schema_registry)

        # Initialize DRFactory instances for each schema type
        user_dr_factory = DRFactory("config/user_schema.yaml")
        device_dr_factory = DRFactory("config/device_schema.yaml")
        device_pairing_dr_factory = DRFactory("config/device_pairing_schema.yaml")
        emergency_contact_dr_factory = DRFactory("config/emergency_contact_schema.yaml")
        climbing_session_dr_factory = DRFactory("config/climbing_session_schema.yaml")
        session_event_dr_factory = DRFactory("config/session_event_schema.yaml")

        # Store references
        self.app.config["SCHEMA_REGISTRY"] = schema_registry
        self.app.config["DB_SERVICE"] = db_service
        self.app.config["DT_FACTORY"] = dt_factory
        self.app.config["USER_DR_FACTORY"] = user_dr_factory
        self.app.config["DEVICE_DR_FACTORY"] = device_dr_factory
        self.app.config["DEVICE_PAIRING_DR_FACTORY"] = device_pairing_dr_factory
        self.app.config["EMERGENCY_CONTACT_DR_FACTORY"] = emergency_contact_dr_factory
        self.app.config["CLIMBING_SESSION_DR_FACTORY"] = climbing_session_dr_factory
        self.app.config["SESSION_EVENT_DR_FACTORY"] = session_event_dr_factory

    def _init_mqtt(self):
        """Initialize MQTT service for device communication"""
        # Only initialize MQTT in the child process to avoid duplicate subscriptions
        if is_running_from_reloader():
            return

        try:
            db_service = self.app.config["DB_SERVICE"]
            dt_factory = self.app.config["DT_FACTORY"]

            # Initialize Telegram service
            telegram_service = None
            try:
                telegram_service = TelegramService(db_service)
                self.app.config["TELEGRAM_SERVICE"] = telegram_service
                self.app.logger.info("Telegram Service initialized successfully")
            except Exception as e:
                self.app.logger.warning(
                    f"Failed to initialize Telegram service: {str(e)}"
                )
                self.app.logger.warning("Continuing without Telegram alerts")

            # Initialize MQTT service with Telegram service
            mqtt_service = MQTTService(db_service, dt_factory, telegram_service)
            mqtt_service.connect()

            self.app.config["MQTT_SERVICE"] = mqtt_service
            self.app.logger.info("MQTT Service initialized successfully")

            # Set bidirectional reference between services
            if telegram_service:
                telegram_service.set_mqtt_service(mqtt_service)
                # Start Telegram bot polling
                telegram_service.start_polling()
                self.app.logger.info("Telegram bot polling started")

        except Exception as e:
            self.app.logger.error(f"Failed to initialize MQTT service: {str(e)}")
            # Continue without MQTT - application can still work for other features

    def _register_blueprints(self):
        """Register all API blueprints"""
        register_api_blueprints(self.app)
        self.app.register_blueprint(auth_bp)

    def run(self, host="0.0.0.0", port=5000, debug=True):
        """Run the Flask server"""
        try:
            self.app.run(host=host, port=port, debug=debug)
        finally:
            # Cleanup on server shutdown
            if "TELEGRAM_SERVICE" in self.app.config:
                self.app.config["TELEGRAM_SERVICE"].stop_polling()
            if "MQTT_SERVICE" in self.app.config:
                self.app.config["MQTT_SERVICE"].disconnect()
            if "DB_SERVICE" in self.app.config:
                self.app.config["DB_SERVICE"].disconnect()


if __name__ == "__main__":
    server = FlaskServer()
    server.run()
