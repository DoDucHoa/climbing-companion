import paho.mqtt.client as mqtt
import json
import yaml
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from src.services.base import BaseService
import uuid


class MQTTService(BaseService):
    def __init__(
        self,
        db_service,
        dt_factory,
        telegram_service=None,
        config_path: str = "config/mqtt_config.yaml",
    ):
        super().__init__()
        self.db_service = db_service
        self.dt_factory = dt_factory
        self.telegram_service = telegram_service
        self.logger = logging.getLogger(__name__)
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
            self.client.subscribe(topics_config["telemetry"], qos=qos)
            self.client.subscribe(topics_config["telegram_response"], qos=qos)

            self.logger.info(f"Subscribed to topic: {topics_config['status']}")
            self.logger.info(f"Subscribed to topic: {topics_config['telemetry']}")
            self.logger.info(
                f"Subscribed to topic: {topics_config['telegram_response']}"
            )
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
            # Topic format: climbing/{serial_number}/status or climbing/{serial_number}
            topic_parts = topic.split("/")
            if len(topic_parts) >= 2:
                serial_number = topic_parts[1]
                message_type = topic_parts[2] if len(topic_parts) >= 3 else "telemetry"

                if message_type == "status":
                    self.handle_status(serial_number, payload)
                elif message_type == "telegram":
                    self.handle_telegram_response(serial_number, payload)
                else:
                    # Handle telemetry (session data)
                    self.handle_telemetry(serial_number, payload)

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

    def handle_telemetry(self, serial_number: str, data: Dict[str, Any]):
        """Handle telemetry (session) data from device"""
        try:
            session_state = data.get("session_state")
            session_id = data.get("session_id")

            if not session_state or not session_id:
                self.logger.error(
                    "Missing session_state or session_id in telemetry data"
                )
                return

            self.logger.info(
                f"Processing {session_state} telemetry for device: {serial_number}, session: {session_id}"
            )

            # Find device by serial number
            device = self._find_device_by_serial(serial_number)
            if not device:
                self.logger.error(f"Device not found: {serial_number}")
                return

            # Get user_id from device pairing
            user_id = self._get_user_from_device(serial_number)
            if not user_id:
                self.logger.error(
                    f"No active pairing found for device: {serial_number}"
                )
                return

            # Handle different session states
            if session_state == "START":
                self._handle_session_start(serial_number, user_id, session_id, data)
            elif session_state == "ACTIVE":
                self._handle_session_active(serial_number, session_id, data)
            elif session_state == "END":
                self._handle_session_end(serial_number, session_id, data)
            elif session_state == "INCIDENT":
                self._handle_session_incident(serial_number, user_id, session_id, data)
            else:
                self.logger.warning(f"Unknown session_state: {session_state}")

        except Exception as e:
            self.logger.error(f"Error handling telemetry: {str(e)}")

    def _handle_session_start(
        self, device_serial: str, user_id: str, session_id: str, data: Dict[str, Any]
    ):
        """Handle START session state - create climbing_session and session_event"""
        try:
            # Import DRFactory here to avoid circular imports
            from src.virtualization.digital_replica.dr_factory import DRFactory

            climbing_session_factory = DRFactory("config/climbing_session_schema.yaml")
            session_event_factory = DRFactory("config/session_event_schema.yaml")

            # Create climbing_session
            session_data = {
                "profile": {"start_at": datetime.utcnow(), "session_state": "START"},
                "data": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "device_serial": device_serial,
                    "start_alt": data.get("alt"),
                    "temp": data.get("temp"),
                    "humidity": data.get("humidity"),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                },
            }

            climbing_session_dr = climbing_session_factory.create_dr(
                "climbing_session", session_data
            )
            self.db_service.save_dr("climbing_session", climbing_session_dr)
            self.logger.info(f"Created climbing_session: {session_id}")

            # Create session_event for START
            event_data = {
                "profile": {"create_at": datetime.utcnow()},
                "data": {
                    "session_id": session_id,
                    "device_serial": device_serial,
                    "alt": data.get("alt"),
                },
            }

            session_event_dr = session_event_factory.create_dr(
                "session_event", event_data
            )
            self.db_service.save_dr("session_event", session_event_dr)
            self.logger.info(f"Created session_event for START: {session_id}")

        except Exception as e:
            self.logger.error(f"Error handling session START: {str(e)}")

    def _handle_session_active(
        self, device_serial: str, session_id: str, data: Dict[str, Any]
    ):
        """Handle ACTIVE session state - update climbing_session and create session_event"""
        try:
            # Import DRFactory here to avoid circular imports
            from src.virtualization.digital_replica.dr_factory import DRFactory

            session_event_factory = DRFactory("config/session_event_schema.yaml")

            # Verify climbing_session exists
            existing_session = self._find_session_by_id(session_id)
            if not existing_session:
                self.logger.error(
                    f"Climbing session not found for ACTIVE state: {session_id}"
                )
                return

            # Update climbing_session state to ACTIVE (only if not already ACTIVE)
            current_state = existing_session.get("profile", {}).get("session_state")
            if current_state != "ACTIVE":
                session_updates = {"profile": {"session_state": "ACTIVE"}}

                self.db_service.update_dr(
                    "climbing_session", existing_session["_id"], session_updates
                )
                self.logger.info(
                    f"Updated climbing_session state to ACTIVE: {session_id}"
                )
            else:
                self.logger.debug(f"Session {session_id} already in ACTIVE state")

            # Create session_event for ACTIVE
            event_data = {
                "profile": {"create_at": datetime.utcnow()},
                "data": {
                    "session_id": session_id,
                    "device_serial": device_serial,
                    "alt": data.get("alt"),
                },
            }

            session_event_dr = session_event_factory.create_dr(
                "session_event", event_data
            )
            self.db_service.save_dr("session_event", session_event_dr)
            self.logger.info(
                f"Created session_event for ACTIVE: {session_id}, alt: {data.get('alt')}"
            )

        except Exception as e:
            self.logger.error(f"Error handling session ACTIVE: {str(e)}")

    def _handle_session_end(
        self, device_serial: str, session_id: str, data: Dict[str, Any]
    ):
        """Handle END session state - update climbing_session and create final session_event"""
        try:
            # Import DRFactory here to avoid circular imports
            from src.virtualization.digital_replica.dr_factory import DRFactory

            session_event_factory = DRFactory("config/session_event_schema.yaml")

            # Find climbing_session
            existing_session = self._find_session_by_id(session_id)
            if not existing_session:
                self.logger.error(
                    f"Climbing session not found for END state: {session_id}"
                )
                return

            # Update climbing_session with end data
            session_updates = {
                "profile": {"session_state": "END"},
                "data": {"end_alt": data.get("alt"), "end_at": datetime.utcnow()},
            }

            self.db_service.update_dr(
                "climbing_session", existing_session["_id"], session_updates
            )
            self.logger.info(f"Updated climbing_session with END data: {session_id}")

            # Create session_event for END
            event_data = {
                "profile": {"create_at": datetime.utcnow()},
                "data": {
                    "session_id": session_id,
                    "device_serial": device_serial,
                    "alt": data.get("alt"),
                },
            }

            session_event_dr = session_event_factory.create_dr(
                "session_event", event_data
            )
            self.db_service.save_dr("session_event", session_event_dr)
            self.logger.info(f"Created session_event for END: {session_id}")

        except Exception as e:
            self.logger.error(f"Error handling session END: {str(e)}")

    def _handle_session_incident(
        self, device_serial: str, user_id: str, session_id: str, data: Dict[str, Any]
    ):
        """Handle INCIDENT session state - update session, create event, and send Telegram alerts"""
        try:
            # Import DRFactory here to avoid circular imports
            from src.virtualization.digital_replica.dr_factory import DRFactory

            session_event_factory = DRFactory("config/session_event_schema.yaml")

            # Find climbing_session
            existing_session = self._find_session_by_id(session_id)
            if not existing_session:
                self.logger.error(
                    f"Climbing session not found for INCIDENT state: {session_id}"
                )
                return

            # Update climbing_session state to INCIDENT
            session_updates = {"profile": {"session_state": "INCIDENT"}}

            self.db_service.update_dr(
                "climbing_session", existing_session["_id"], session_updates
            )
            self.logger.info(
                f"Updated climbing_session state to INCIDENT: {session_id}"
            )

            # Create session_event for INCIDENT
            event_data = {
                "profile": {"create_at": datetime.utcnow()},
                "data": {
                    "session_id": session_id,
                    "device_serial": device_serial,
                    "alt": data.get("alt"),
                },
            }

            session_event_dr = session_event_factory.create_dr(
                "session_event", event_data
            )
            self.db_service.save_dr("session_event", session_event_dr)
            self.logger.info(f"Created session_event for INCIDENT: {session_id}")

            # Send emergency alert via Telegram
            if self.telegram_service:
                self.logger.info(
                    f"Sending emergency alert for user: {user_id}, session: {session_id}"
                )

                alert_result = self.telegram_service.send_emergency_alert(
                    user_id=user_id,
                    session_id=session_id,
                    latitude=data.get("latitude"),
                    longitude=data.get("longitude"),
                    altitude=data.get("alt"),
                    device_serial=device_serial,
                )

                self.logger.info(f"Telegram alert result: {alert_result}")
            else:
                self.logger.warning(
                    "Telegram service not available - emergency alert not sent"
                )

        except Exception as e:
            self.logger.error(f"Error handling session INCIDENT: {str(e)}")

    def _get_user_from_device(self, device_serial: str) -> Optional[str]:
        """Get user_id from device_pairing by device serial number"""
        try:
            pairing_collection = self.db_service.db["device_pairing_collection"]

            # Find active pairing for this device
            pairing = pairing_collection.find_one(
                {"data.device_serial": device_serial, "data.pairing_status": "active"}
            )

            if pairing:
                return pairing["data"]["user_id"]

            return None

        except Exception as e:
            self.logger.error(f"Error getting user from device pairing: {str(e)}")
            return None

    def _find_session_by_id(self, session_id: str) -> Optional[Dict]:
        """Find climbing_session by session_id"""
        try:
            collection = self.db_service.db["climbing_session_collection"]
            session = collection.find_one({"data.session_id": session_id})
            return session
        except Exception as e:
            self.logger.error(f"Error finding session: {str(e)}")
            return None

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

    def request_device_status(
        self, device_serial: str, request_data: Dict[str, Any]
    ) -> bool:
        """Request status from device for Telegram bot"""
        try:
            if not self.connected:
                self.logger.error("MQTT not connected - cannot send request")
                return False

            # Build request topic: climbing/{serial}/request
            topic = self.config["mqtt"]["topics"]["device_request"].format(
                serial=device_serial
            )
            qos = self.config["mqtt"]["qos"]["publish"]

            # Add timestamp
            request_data["timestamp"] = datetime.utcnow().isoformat()

            # Publish request
            payload = json.dumps(request_data)
            result = self.client.publish(topic, payload, qos=qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Status request sent to device: {device_serial}")
                return True
            else:
                self.logger.error(f"Failed to publish request: {result.rc}")
                return False

        except Exception as e:
            self.logger.error(f"Error requesting device status: {str(e)}")
            return False

    def handle_telegram_response(self, serial_number: str, data: Dict[str, Any]):
        """Handle response from device for Telegram status check"""
        try:
            self.logger.info(
                f"Processing Telegram response from device: {serial_number}"
            )

            # Extract data from response
            chat_id = data.get("chat_id")
            user_name = data.get("user_name")
            session_state = data.get("session_state", "UNKNOWN")
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            altitude = data.get("alt")
            temperature = data.get("temp")
            humidity = data.get("humidity")
            session_id = data.get("session_id")

            if not chat_id:
                self.logger.error("No chat_id in Telegram response")
                return

            # Send response via Telegram service
            if self.telegram_service:
                self.telegram_service.send_status_response(
                    chat_id=str(chat_id),
                    user_name=user_name or "Unknown",
                    session_state=session_state,
                    latitude=latitude,
                    longitude=longitude,
                    altitude=altitude,
                    temperature=temperature,
                    humidity=humidity,
                    device_serial=serial_number,
                    session_id=session_id,
                )
                self.logger.info(f"Status response sent to chat_id: {chat_id}")
            else:
                self.logger.error("Telegram service not available")

        except Exception as e:
            self.logger.error(f"Error handling Telegram response: {str(e)}")

    def execute(
        self, data: Dict, dr_type: Optional[str] = None, attribute: Optional[str] = None
    ):
        """Execute service - required by BaseService"""
        # This service runs continuously, not on-demand
        return {"status": "MQTT service running", "connected": self.connected}
