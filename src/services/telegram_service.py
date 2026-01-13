import logging
from typing import Dict, Any, Optional, List
import yaml
import requests
import threading
import time


class TelegramService:
    def __init__(self, db_service, config_path: str = "config/telegram_config.yaml"):
        self.db_service = db_service
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.bot_token = None
        self.api_url = None
        self.mqtt_service = None  # Will be set later
        self.polling_thread = None
        self.polling_active = False
        self.last_update_id = 0
        self.pending_status_checks = {}  # Track pending status check requests
        self._init_bot()

    def _load_config(self, path: str) -> Dict:
        try:
            with open(path, "r") as file:
                config = yaml.safe_load(file)
                return config
        except Exception as e:
            self.logger.error(f"Failed to load Telegram config: {str(e)}")
            raise ValueError(f"Invalid Telegram configuration: {str(e)}")

    def _init_bot(self):
        try:
            self.bot_token = self.config.get("telegram", {}).get("bot_token")
            if not self.bot_token:
                raise ValueError("Bot token not found in configuration")

            self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
            self.logger.info("Telegram bot initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {str(e)}")
            raise

    def _get_emergency_contacts(self, user_id: str) -> List[Dict]:
        try:
            collection = self.db_service.db["emergency_contact_collection"]

            # Find all active emergency contacts for this user
            contacts = collection.find(
                {"data.user_id": user_id, "data.is_active": True}
            )

            return list(contacts)
        except Exception as e:
            self.logger.error(f"Error retrieving emergency contacts: {str(e)}")
            return []

    def _format_alert_message(
        self,
        user_name: str,
        session_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        device_serial: Optional[str] = None,
    ) -> str:
        message = f"*EMERGENCY ALERT*\n\n"
        message += f"Incident detected for: *{user_name}*\n\n"
        message += f"*Location Details:*\n"

        if latitude is not None and longitude is not None:
            message += f"• Latitude: `{latitude}`\n"
            message += f"• Longitude: `{longitude}`\n"
            # Google Maps link
            maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
            message += f"• [View on Google Maps]({maps_url})\n"
        else:
            message += f"• Location: _Not available_\n"

        message += f"\n*Device:* `{device_serial or 'Unknown'}`\n"
        message += f"*Session ID:* `{session_id}`\n\n"

        return message

    def _send_telegram_message(self, chat_id: str, message: str) -> bool:
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}

            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                self.logger.info(f"Alert sent to Telegram chat_id: {chat_id}")
                return True
            else:
                error_msg = response.json().get("description", "Unknown error")
                self.logger.error(
                    f"Failed to send Telegram message to {chat_id}: {error_msg}"
                )
                return False

        except requests.exceptions.Timeout:
            self.logger.error(f"Timeout sending Telegram message to {chat_id}")
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error(
                f"Request error sending Telegram message to {chat_id}: {str(e)}"
            )
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram message: {str(e)}")
            return False

    def send_emergency_alert(
        self,
        user_id: str,
        session_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        device_serial: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            # Get user information
            user = self._get_user_info(user_id)
            if not user:
                self.logger.error(f"User not found: {user_id}")
                return {"status": "error", "message": "User not found", "sent_count": 0}

            user_name = user.get("profile", {}).get("name", "Unknown User")

            # Get emergency contacts
            contacts = self._get_emergency_contacts(user_id)

            if not contacts:
                self.logger.warning(f"No emergency contacts found for user: {user_id}")
                return {
                    "status": "warning",
                    "message": "No emergency contacts configured",
                    "sent_count": 0,
                }

            # Format alert message
            message = self._format_alert_message(
                user_name=user_name,
                session_id=session_id,
                latitude=latitude,
                longitude=longitude,
                altitude=altitude,
                device_serial=device_serial,
            )

            # Send alerts to all contacts
            sent_count = 0
            failed_contacts = []

            for contact in contacts:
                telegram_chat_id = contact.get("profile", {}).get("telegram_chat_id")
                contact_name = contact.get("profile", {}).get("name", "Unknown")

                if not telegram_chat_id:
                    self.logger.warning(
                        f"No Telegram chat_id for contact: {contact_name}"
                    )
                    failed_contacts.append(contact_name)
                    continue

                # Send message synchronously
                try:
                    success = self._send_telegram_message(telegram_chat_id, message)

                    if success:
                        sent_count += 1
                        self.logger.info(f"Alert sent to contact: {contact_name}")
                    else:
                        failed_contacts.append(contact_name)
                except Exception as e:
                    self.logger.error(f"Error sending to {contact_name}: {str(e)}")
                    failed_contacts.append(contact_name)

            # Prepare result
            result = {
                "status": "success" if sent_count > 0 else "error",
                "message": f"Alert sent to {sent_count} of {len(contacts)} contacts",
                "sent_count": sent_count,
                "total_contacts": len(contacts),
            }

            if failed_contacts:
                result["failed_contacts"] = failed_contacts

            self.logger.info(
                f"Emergency alert completed: {sent_count}/{len(contacts)} sent"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error sending emergency alert: {str(e)}")
            return {"status": "error", "message": str(e), "sent_count": 0}

    def _get_user_info(self, user_id: str) -> Optional[Dict]:
        try:
            collection = self.db_service.db["user_collection"]
            user = collection.find_one({"_id": user_id})
            return user
        except Exception as e:
            self.logger.error(f"Error retrieving user info: {str(e)}")
            return None

    def set_mqtt_service(self, mqtt_service):
        """Set MQTT service reference for sending device requests"""
        self.mqtt_service = mqtt_service
        self.logger.info("MQTT service reference set for Telegram bot")

    def start_polling(self):
        """Start Telegram bot polling in a separate thread"""
        if self.polling_active:
            self.logger.warning("Telegram polling already active")
            return

        self.polling_active = True
        self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.polling_thread.start()
        self.logger.info("Telegram bot polling started")

    def stop_polling(self):
        """Stop Telegram bot polling"""
        self.polling_active = False
        if self.polling_thread:
            self.polling_thread.join(timeout=5)
        self.logger.info("Telegram bot polling stopped")

    def _polling_loop(self):
        """Main polling loop to get updates from Telegram"""
        self.logger.info("Telegram polling loop started")

        while self.polling_active:
            try:
                # Get updates from Telegram
                updates = self._get_updates()

                if updates:
                    for update in updates:
                        self._process_update(update)
                        # Update last_update_id to acknowledge this update
                        self.last_update_id = update.get("update_id", 0)

                # Sleep briefly to avoid hammering the API
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in polling loop: {str(e)}")
                time.sleep(5)  # Wait longer on error

    def _get_updates(self) -> List[Dict]:
        """Get updates from Telegram using long polling"""
        try:
            url = f"{self.api_url}/getUpdates"
            params = {
                "offset": self.last_update_id + 1,
                "timeout": 30,  # Long polling timeout
                "allowed_updates": ["message"],
            }

            response = requests.get(url, params=params, timeout=35)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return result.get("result", [])
            else:
                self.logger.error(f"Failed to get updates: {response.status_code}")

        except requests.exceptions.Timeout:
            # Timeout is normal for long polling
            pass
        except Exception as e:
            self.logger.error(f"Error getting updates: {str(e)}")

        return []

    def _process_update(self, update: Dict):
        """Process a single update from Telegram"""
        try:
            message = update.get("message")
            if not message:
                return

            chat_id = message.get("chat", {}).get("id")
            text = message.get("text", "")

            if not chat_id:
                return

            self.logger.info(f"Received message from chat_id {chat_id}: {text}")

            # Handle commands
            if text.startswith("/"):
                self._handle_command(chat_id, text)

        except Exception as e:
            self.logger.error(f"Error processing update: {str(e)}")

    def _handle_command(self, chat_id: int, command: str):
        """Handle Telegram bot commands"""
        try:
            command = command.strip().lower()

            if command == "/check_status":
                self._handle_check_status(chat_id)
            elif command == "/start":
                self._send_telegram_message(
                    str(chat_id),
                    "*Climbing Companion Bot*\n\n"
                    "Available commands:\n"
                    "/check_status - Get current location and status of your climber",
                )
            else:
                self._send_telegram_message(
                    str(chat_id),
                    f"Unknown command: {command}\n\n"
                    "Available commands:\n"
                    "/check_status - Get current location and status",
                )

        except Exception as e:
            self.logger.error(f"Error handling command: {str(e)}")

    def _handle_check_status(self, chat_id: int):
        """Handle /check_status command from emergency contact"""
        try:
            self.logger.info(f"Processing /check_status from chat_id: {chat_id}")

            # Find emergency contact by telegram_chat_id
            emergency_contact = self._find_emergency_contact_by_chat_id(str(chat_id))

            if not emergency_contact:
                self._send_telegram_message(
                    str(chat_id),
                    "❌ You are not registered as an emergency contact.\n\n"
                    "Please contact the climber to add you as an emergency contact.",
                )
                return

            # Get user_id from emergency contact
            user_id = emergency_contact.get("data", {}).get("user_id")
            contact_name = emergency_contact.get("profile", {}).get(
                "name", "Emergency Contact"
            )

            if not user_id:
                self._send_telegram_message(
                    str(chat_id),
                    "❌ Error: User ID not found in emergency contact record.",
                )
                return

            # Get user info
            user = self._get_user_info(user_id)
            if not user:
                self._send_telegram_message(str(chat_id), "❌ Error: User not found.")
                return

            user_name = user.get("profile", {}).get("name", "Unknown")

            # Find active device for user
            device = self._find_user_active_device(user_id)

            if not device:
                self._send_telegram_message(
                    str(chat_id),
                    f"⚠️ No active device found for *{user_name}*.\n\n"
                    "The climber may not have a device paired or the device is offline.",
                )
                return

            device_serial = device.get("profile", {}).get("serial_number")

            # Send "processing" message
            self._send_telegram_message(
                str(chat_id),
                f"Requesting status from *{user_name}*'s device...\n\n"
                f"Device: `{device_serial}`",
            )

            # Request data from device via MQTT
            if self.mqtt_service:
                request_data = {
                    "request_type": "status_check",
                    "chat_id": str(chat_id),
                    "user_id": user_id,
                    "user_name": user_name,
                    "contact_name": contact_name,
                }

                success = self.mqtt_service.request_device_status(
                    device_serial, request_data
                )

                if not success:
                    self._send_telegram_message(
                        str(chat_id),
                        "❌ Failed to send request to device.\n\n"
                        "The device may be offline or unreachable.",
                    )
                else:
                    # Add to pending requests
                    request_key = f"{chat_id}_{user_id}"
                    self.pending_status_checks[request_key] = {
                        "chat_id": str(chat_id),
                        "user_id": user_id,
                        "user_name": user_name,
                        "timestamp": time.time(),
                    }

                    # Start timeout handler in background thread
                    timeout_thread = threading.Thread(
                        target=self._handle_status_check_timeout,
                        args=(str(chat_id), user_id, user_name),
                        daemon=True,
                    )
                    timeout_thread.start()
            else:
                self._send_telegram_message(
                    str(chat_id), "❌ Error: MQTT service not available."
                )

        except Exception as e:
            self.logger.error(f"Error handling check_status: {str(e)}")
            self._send_telegram_message(
                str(chat_id), f"❌ Error processing request: {str(e)}"
            )

    def _find_emergency_contact_by_chat_id(self, chat_id: str) -> Optional[Dict]:
        """Find emergency contact by Telegram chat_id"""
        try:
            collection = self.db_service.db["emergency_contact_collection"]
            contact = collection.find_one({"profile.telegram_chat_id": chat_id})
            return contact
        except Exception as e:
            self.logger.error(f"Error finding emergency contact: {str(e)}")
            return None

    def _find_user_active_device(self, user_id: str) -> Optional[Dict]:
        """Find active paired device for user"""
        try:
            # Find active device pairing
            pairing_collection = self.db_service.db["device_pairing_collection"]
            pairing = pairing_collection.find_one(
                {"data.user_id": user_id, "data.pairing_status": "active"}
            )

            if not pairing:
                return None

            device_serial = pairing.get("data", {}).get("device_serial")

            # Get device
            device_collection = self.db_service.db["device_collection"]
            device = device_collection.find_one(
                {"_id": device_serial, "data.status": "active"}
            )

            return device

        except Exception as e:
            self.logger.error(f"Error finding active device: {str(e)}")
            return None

    def _has_active_session(self, user_id: str) -> bool:
        """Check if user has any active or started climbing sessions"""
        try:
            session_collection = self.db_service.db["climbing_session_collection"]
            active_session = session_collection.find_one(
                {
                    "data.user_id": user_id,
                    "data.session_state": {"$in": ["ACTIVE", "START"]},
                }
            )
            return active_session is not None
        except Exception as e:
            self.logger.error(f"Error checking active sessions: {str(e)}")
            return False

    def _handle_status_check_timeout(self, chat_id: str, user_id: str, user_name: str):
        """Handle timeout for status check - send notification if no active session"""
        try:
            # Wait 10 seconds
            time.sleep(10)

            # Check if request still pending (not responded)
            request_key = f"{chat_id}_{user_id}"
            if request_key not in self.pending_status_checks:
                # Already responded, do nothing
                self.logger.info(f"Status check already responded for: {request_key}")
                return

            # Remove from pending
            del self.pending_status_checks[request_key]
            self.logger.info(f"Status check timed out for: {request_key}")

            # Check if user has active session
            has_active = self._has_active_session(user_id)

            if not has_active:
                # No active session - send notification
                message = (
                    f"*Status Update for {user_name}*\n\n"
                    f"The climber is currently not in an active climbing session, or:\n"
                    f"• The device is not in an area with internet connectivity\n"
                    f"• The climber has not started their activity yet"
                )
                self._send_telegram_message(chat_id, message)
                self.logger.info(
                    f"Sent no-active-session notification to chat_id: {chat_id}"
                )
            else:
                # Has active session but device didn't respond - likely connectivity issue
                message = (
                    f"*Status Update for {user_name}*\n\n"
                    f"Unable to get current status from device.\n\n"
                    f"The climber has an active session, but:\n"
                    f"• The device may not be in an area with internet connectivity\n"
                    f"• There may be a temporary connection issue"
                )
                self._send_telegram_message(chat_id, message)
                self.logger.info(
                    f"Sent device-unreachable notification to chat_id: {chat_id}"
                )

        except Exception as e:
            self.logger.error(f"Error handling status check timeout: {str(e)}")

    def send_status_response(
        self,
        chat_id: str,
        user_name: str,
        session_state: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        device_serial: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Send status response back to emergency contact"""
        try:
            # Remove from pending requests - critical to prevent timeout firing
            if user_id:
                request_key = f"{chat_id}_{user_id}"
                if request_key in self.pending_status_checks:
                    del self.pending_status_checks[request_key]
                    self.logger.info(f"Removed pending status check: {request_key}")
                else:
                    self.logger.warning(f"Pending status check not found: {request_key}")
            else:
                # Fallback: if user_id not provided, try to find and remove by chat_id
                self.logger.warning(f"user_id not provided in status response for chat_id: {chat_id}")
                keys_to_remove = [key for key in self.pending_status_checks.keys() if key.startswith(f"{chat_id}_")]
                for key in keys_to_remove:
                    del self.pending_status_checks[key]
                    self.logger.info(f"Removed pending status check by chat_id match: {key}")

            message = f"*Status Update for {user_name}*\n\n"

            # Session state
            state_emoji = {"START": "🟢", "ACTIVE": "🟡", "END": "⚫", "INCIDENT": "🔴"}
            emoji = state_emoji.get(session_state, "⚪")
            message += f"*Session State:* {emoji} `{session_state}`\n\n"

            # Location
            message += f"*Location:*\n"
            if latitude is not None and longitude is not None:
                message += f"• Latitude: `{latitude:.6f}`\n"
                message += f"• Longitude: `{longitude:.6f}`\n"
                maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
                message += f"• [View on Google Maps]({maps_url})\n"
            else:
                message += f"• Location: _Not available_\n"

            # Environmental data
            if temperature is not None or humidity is not None:
                message += f"\n*Environmental:*\n"
                if temperature is not None:
                    message += f"• Temperature: `{temperature:.1f}`°C\n"
                if humidity is not None:
                    message += f"• Humidity: `{humidity:.1f}`%\n"

            # Device info
            message += f"\n*Device:* `{device_serial or 'Unknown'}`\n"

            message += f"\n_Last updated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}_"

            self._send_telegram_message(chat_id, message)
            self.logger.info(f"Status response sent to chat_id: {chat_id}")

        except Exception as e:
            self.logger.error(f"Error sending status response: {str(e)}")
