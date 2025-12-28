import paho.mqtt.client as mqtt
import json
import yaml
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from src.services.base import BaseService
import uuid

logger = logging.getLogger(__name__)


class MQTTService(BaseService):
    def __init__(
        self,
        db_service,
        dt_factory,
        config_path: str = "config/mqtt_config.yaml",
    ):
        super().__init__()
        self.db_service = db_service
        self.dt_factory = dt_factory
        self.logger = logging.getLogger(__name__)  # Initialize logger first
        self.config = self._load_config(config_path)
        self.client = None
        self.connected = False

    def _load_config(self, path: str) -> Dict:
        """Load MQTT configuration from YAML file"""
        try:
            with open(path, "r") as file:
                return yaml.safe_load(file)
        except Exception as e:
            self.logger.error(f"Failed to load MQTT config: {str(e)}")
            # Return default config
            return {
                "mqtt": {
                    "broker": {
                        "host": "broker.hivemq.com",
                        "port": 1883,
                        "keepalive": 60,
                    },
                    "topics": {
                        "status": "climbing/+/status",
                    },
                    "qos": {"subscribe": 1, "publish": 1},
                    "client": {
                        "id_prefix": "climbing_companion_",
                        "clean_session": True,
                    },
                }
            }

    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            broker_config = self.config["mqtt"]["broker"]
            client_config = self.config["mqtt"]["client"]

            # Create client with unique ID
            client_id = f"{client_config['id_prefix']}{uuid.uuid4().hex[:8]}"
            self.client = mqtt.Client(
                client_id=client_id,
                clean_session=client_config.get("clean_session", True),
            )

            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect

            # Connect to broker
            self.logger.info(
                f"Connecting to MQTT broker at {broker_config['host']}:{broker_config['port']}"
            )
            self.client.connect(
                broker_config["host"],
                broker_config["port"],
                broker_config.get("keepalive", 60),
            )

            # Start the loop in a separate thread
            self.client.loop_start()

            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {str(e)}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            self.logger.info("Connected to MQTT broker successfully")

            # Subscribe to topics
            topics_config = self.config["mqtt"]["topics"]
            qos = self.config["mqtt"]["qos"]["subscribe"]

            self.client.subscribe(topics_config["status"], qos=qos)

            self.logger.info(f"Subscribed to topic: {topics_config['status']}")
        else:
            self.logger.error(f"Connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        if rc != 0:
            self.logger.warning(f"Unexpected disconnect from MQTT broker (code: {rc})")
        else:
            self.logger.info("Disconnected from MQTT broker")

    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            self.logger.info(f"Received message on topic: {topic}")
            self.logger.debug(f"Payload: {payload}")

            # Extract serial number from topic
            # Topic format: climbing/{serial_number}/status
            topic_parts = topic.split("/")
            if len(topic_parts) >= 3:
                serial_number = topic_parts[1]
                message_type = topic_parts[2]

                if message_type == "status":
                    self.handle_status(serial_number, payload)

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON payload: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")

    def handle_status(self, serial_number: str, data: Dict[str, Any]):
        """Handle status update from device"""
        try:
            self.logger.info(f"Processing status update for device: {serial_number}")

            # Find device by serial number
            device = self._find_device_by_serial(serial_number)

            if not device:
                self.logger.warning(
                    f"Device not found for status update: {serial_number}"
                )
                return

            status = data.get("status", "active")

            # Check if this is first connection (device was inactive)
            if device["data"].get("status") == "inactive" and status == "active":
                self.logger.info(
                    f"Device {serial_number} connected for first time, activating..."
                )
                # Update to active
                status = "active"

                # Try to auto-pair if not already paired
                self._auto_pair_device(device["_id"], serial_number)

            # Update device status
            device_updates = {
                "data": {"status": status, "last_sync_at": datetime.utcnow()}
            }

            self.db_service.update_dr("device", device["_id"], device_updates)
            self.logger.info(f"Device status updated: {serial_number} -> {status}")

        except Exception as e:
            self.logger.error(f"Error handling status update: {str(e)}")

    def _find_device_by_serial(self, serial_number: str) -> Optional[Dict]:
        """Find device DR by serial number"""
        try:
            collection = self.db_service.db["device_collection"]
            device = collection.find_one({"profile.serial_number": serial_number})
            return device
        except Exception as e:
            self.logger.error(f"Error finding device: {str(e)}")
            return None

    def _auto_pair_device(self, device_serial: str, serial_number: str):
        """Auto-pair device with user who registered it"""
        try:
            # Find user who registered this device
            # This requires tracking user_id when device is registered
            # For now, we'll create pairing if it doesn't exist

            pairing_collection = self.db_service.db["device_pairing_collection"]

            # Check if pairing already exists
            existing_pairing = pairing_collection.find_one(
                {"data.device_serial": device_serial}
            )

            if existing_pairing:
                self.logger.info(f"Pairing already exists for device {serial_number}")
                return

            # Get user_id from device metadata or session
            # For now, we'll log that pairing needs to be created manually
            self.logger.info(
                f"Auto-pairing not completed - user_id needed for device {serial_number}"
            )

        except Exception as e:
            self.logger.error(f"Error auto-pairing device: {str(e)}")

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            self.logger.info("Disconnected from MQTT broker")

    def execute(self, data: Dict, dr_type: str = None, attribute: str = None):
        """Execute service - required by BaseService"""
        # This service runs continuously, not on-demand
        return {"status": "MQTT service running", "connected": self.connected}
