import logging
from typing import Dict, Any, Optional, List
import yaml
import requests
from urllib.parse import quote


class TelegramService:
    def __init__(self, db_service, config_path: str = "config/telegram_config.yaml"):
        self.db_service = db_service
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        self.bot_token = None
        self.api_url = None
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

        if altitude is not None:
            message += f"• Altitude: `{altitude}` meters\n"

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