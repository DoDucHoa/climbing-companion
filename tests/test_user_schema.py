import pytest
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.virtualization.digital_replica.dr_factory import DRFactory
from src.virtualization.digital_replica.schema_registry import SchemaRegistry


class TestUserSchema:
    """Test suite for user_schema.yaml"""

    @pytest.fixture
    def dr_factory(self):
        """Create DRFactory instance with user schema"""
        schema_path = os.path.join("config", "user_schema.yaml")
        return DRFactory(schema_path)

    @pytest.fixture
    def schema_registry(self):
        """Create SchemaRegistry instance with user schema"""
        registry = SchemaRegistry()
        schema_path = os.path.join("config", "user_schema.yaml")
        registry.load_schema("user", schema_path)
        return registry

    def test_schema_loading(self, dr_factory):
        """Test that user schema loads correctly"""
        assert dr_factory.schema is not None
        assert "schemas" in dr_factory.schema
        assert "common_fields" in dr_factory.schema["schemas"]
        assert "entity" in dr_factory.schema["schemas"]
        assert "validations" in dr_factory.schema["schemas"]

    def test_create_user_with_minimal_data(self, dr_factory):
        """Test creating user with only mandatory fields"""
        initial_data = {
            "profile": {"name": "Alice Johnson", "email": "alice@example.com"}
        }

        dr = dr_factory.create_dr("user", initial_data)

        # Check basic structure
        assert dr["_id"] is not None
        assert dr["type"] == "user"
        assert dr["profile"]["name"] == "Alice Johnson"
        assert dr["profile"]["email"] == "alice@example.com"

        # Check initialization defaults
        assert dr["data"]["is_active"] == True
        assert dr["data"]["user_preferences"] == {}
        assert dr["data"]["notification_settings"] == {}

        # Check metadata
        assert "created_at" in dr["metadata"]
        assert "updated_at" in dr["metadata"]
        assert isinstance(dr["metadata"]["created_at"], datetime)

    def test_create_user_with_complete_data(self, dr_factory):
        """Test creating user with all fields"""
        dob = datetime(1990, 5, 15)
        initial_data = {
            "profile": {
                "name": "Bob Smith",
                "email": "bob.smith@example.com",
                "phone": "+1234567890",
                "date_of_birth": dob,
            },
            "data": {
                "user_preferences": {"theme": "dark", "language": "en"},
                "profile_picture_url": "https://example.com/profile.jpg",
                "is_active": True,
                "notification_settings": {"email": True, "sms": False, "push": True},
            },
        }

        dr = dr_factory.create_dr("user", initial_data)

        assert dr["profile"]["name"] == "Bob Smith"
        assert dr["profile"]["email"] == "bob.smith@example.com"
        assert dr["profile"]["phone"] == "+1234567890"
        assert dr["profile"]["date_of_birth"] == dob
        assert dr["data"]["user_preferences"]["theme"] == "dark"
        assert dr["data"]["user_preferences"]["language"] == "en"
        assert dr["data"]["profile_picture_url"] == "https://example.com/profile.jpg"
        assert dr["data"]["is_active"] == True
        assert dr["data"]["notification_settings"]["email"] == True
        assert dr["data"]["notification_settings"]["sms"] == False
        assert dr["data"]["notification_settings"]["push"] == True

    def test_email_pattern_validation(self, dr_factory):
        """Test email pattern validation"""
        # Valid emails
        valid_emails = [
            "user@example.com",
            "user.name@example.co.uk",
            "user+tag@example.com",
            "test123@test.org",
        ]
        for email in valid_emails:
            initial_data = {"profile": {"name": "Test User", "email": email}}
            dr = dr_factory.create_dr("user", initial_data)
            assert dr["profile"]["email"] == email

        # Invalid emails
        invalid_emails = ["invalid", "user@", "@example.com", "user@example", "user"]
        for email in invalid_emails:
            with pytest.raises(ValueError) as exc_info:
                initial_data = {"profile": {"name": "Test User", "email": email}}
                dr_factory.create_dr("user", initial_data)
            assert "does not match required pattern" in str(exc_info.value)

    def test_phone_pattern_validation(self, dr_factory):
        """Test phone number pattern validation"""
        # Valid phone numbers
        valid_phones = [
            "+1234567890",
            "1234567890",
            "+123456789012345",
            "+4401234567890",
        ]
        for phone in valid_phones:
            initial_data = {
                "profile": {
                    "name": "Test User",
                    "email": "test@example.com",
                    "phone": phone,
                }
            }
            dr = dr_factory.create_dr("user", initial_data)
            assert dr["profile"]["phone"] == phone

        # Invalid phone numbers
        invalid_phones = [
            "123",
            "+12345",
            "abc1234567",
            "123-456-7890",
            "(123) 456-7890",
        ]
        for phone in invalid_phones:
            with pytest.raises(ValueError) as exc_info:
                initial_data = {
                    "profile": {
                        "name": "Test User",
                        "email": "test@example.com",
                        "phone": phone,
                    }
                }
                dr_factory.create_dr("user", initial_data)
            assert "does not match required pattern" in str(exc_info.value)

    def test_missing_mandatory_fields(self, dr_factory):
        """Test that missing mandatory fields raise errors"""
        # Missing name in profile
        with pytest.raises(ValueError):
            dr_factory.create_dr("user", {"profile": {"email": "test@example.com"}})

        # Missing email in profile
        with pytest.raises(ValueError):
            dr_factory.create_dr("user", {"profile": {"name": "Test User"}})

        # Missing both
        with pytest.raises(ValueError):
            dr_factory.create_dr("user", {"profile": {}})

    def test_update_user(self, dr_factory):
        """Test updating user DR"""
        # Create initial user
        initial_data = {
            "profile": {"name": "Charlie Brown", "email": "charlie@example.com"}
        }
        dr = dr_factory.create_dr("user", initial_data)

        # Update user preferences and add phone
        updates = {
            "profile": {"phone": "+1234567890"},
            "data": {
                "user_preferences": {"theme": "light", "notifications": "enabled"},
                "profile_picture_url": "https://example.com/new-profile.jpg",
            },
        }
        updated_dr = dr_factory.update_dr(dr, updates)

        assert updated_dr["profile"]["phone"] == "+1234567890"
        assert updated_dr["data"]["user_preferences"]["theme"] == "light"
        assert updated_dr["data"]["user_preferences"]["notifications"] == "enabled"
        assert (
            updated_dr["data"]["profile_picture_url"]
            == "https://example.com/new-profile.jpg"
        )
        assert updated_dr["metadata"]["updated_at"] > dr["metadata"]["updated_at"]

    def test_update_with_invalid_data(self, dr_factory):
        """Test that updates validate constraints"""
        # Create initial user
        initial_data = {"profile": {"name": "Test User", "email": "test@example.com"}}
        dr = dr_factory.create_dr("user", initial_data)

        # Try to update with invalid email
        with pytest.raises(ValueError):
            updates = {"profile": {"email": "invalid-email"}}
            dr_factory.update_dr(dr, updates)

        # Try to update with invalid phone
        with pytest.raises(ValueError):
            updates = {"profile": {"phone": "123"}}
            dr_factory.update_dr(dr, updates)

    def test_schema_registry_conversion(self, schema_registry):
        """Test SchemaRegistry MongoDB schema conversion"""
        validation_schema = schema_registry.get_validation_schema("user")

        assert "$jsonSchema" in validation_schema
        json_schema = validation_schema["$jsonSchema"]

        # Check required fields
        assert "_id" in json_schema["required"]
        assert "type" in json_schema["required"]

        # Check properties structure
        assert "properties" in json_schema
        assert "_id" in json_schema["properties"]
        assert "type" in json_schema["properties"]
        assert "profile" in json_schema["properties"]
        assert "data" in json_schema["properties"]
        assert "metadata" in json_schema["properties"]

    def test_collection_name(self, schema_registry):
        """Test collection name generation"""
        collection_name = schema_registry.get_collection_name("user")
        assert collection_name == "user_collection"

    def test_is_active_default(self, dr_factory):
        """Test is_active default value"""
        initial_data = {"profile": {"name": "Test User", "email": "test@example.com"}}
        dr = dr_factory.create_dr("user", initial_data)
        assert dr["data"]["is_active"] == True

        # Explicitly set to False
        initial_data = {
            "profile": {"name": "Inactive User", "email": "inactive@example.com"},
            "data": {"is_active": False},
        }
        dr = dr_factory.create_dr("user", initial_data)
        assert dr["data"]["is_active"] == False

    def test_user_preferences_dict(self, dr_factory):
        """Test user_preferences accepts nested dictionary"""
        initial_data = {
            "profile": {"name": "Test User", "email": "test@example.com"},
            "data": {
                "user_preferences": {
                    "theme": "dark",
                    "language": "en",
                    "timezone": "UTC",
                    "display": {"density": "compact", "font_size": 14},
                }
            },
        }

        dr = dr_factory.create_dr("user", initial_data)

        assert dr["data"]["user_preferences"]["theme"] == "dark"
        assert dr["data"]["user_preferences"]["language"] == "en"
        assert dr["data"]["user_preferences"]["timezone"] == "UTC"
        assert dr["data"]["user_preferences"]["display"]["density"] == "compact"
        assert dr["data"]["user_preferences"]["display"]["font_size"] == 14

    def test_notification_settings_dict(self, dr_factory):
        """Test notification_settings accepts nested dictionary"""
        initial_data = {
            "profile": {"name": "Test User", "email": "test@example.com"},
            "data": {
                "notification_settings": {
                    "email": True,
                    "sms": False,
                    "push": True,
                    "frequency": {"daily_digest": True, "instant": False},
                }
            },
        }

        dr = dr_factory.create_dr("user", initial_data)

        assert dr["data"]["notification_settings"]["email"] == True
        assert dr["data"]["notification_settings"]["sms"] == False
        assert dr["data"]["notification_settings"]["push"] == True
        assert dr["data"]["notification_settings"]["frequency"]["daily_digest"] == True
        assert dr["data"]["notification_settings"]["frequency"]["instant"] == False

    def test_datetime_fields(self, dr_factory):
        """Test datetime field handling"""
        dob = datetime(1985, 3, 20)
        initial_data = {
            "profile": {
                "name": "Test User",
                "email": "test@example.com",
                "date_of_birth": dob,
            }
        }

        dr = dr_factory.create_dr("user", initial_data)

        assert dr["profile"]["date_of_birth"] == dob
        assert isinstance(dr["metadata"]["created_at"], datetime)
        assert isinstance(dr["metadata"]["updated_at"], datetime)

    def test_optional_fields_not_required(self, dr_factory):
        """Test that optional fields can be omitted"""
        # Create user without optional profile fields
        initial_data = {
            "profile": {"name": "Minimal User", "email": "minimal@example.com"}
        }
        dr = dr_factory.create_dr("user", initial_data)

        # These optional fields should not exist or be None
        assert "phone" not in dr["profile"] or dr["profile"].get("phone") is None
        assert (
            "date_of_birth" not in dr["profile"]
            or dr["profile"].get("date_of_birth") is None
        )

    def test_update_nested_preferences(self, dr_factory):
        """Test updating nested preference structures"""
        # Create user with initial preferences
        initial_data = {
            "profile": {"name": "Test User", "email": "test@example.com"},
            "data": {"user_preferences": {"theme": "light", "language": "en"}},
        }
        dr = dr_factory.create_dr("user", initial_data)

        # Update and add new preferences
        updates = {
            "data": {
                "user_preferences": {
                    "theme": "dark",
                    "language": "en",
                    "new_setting": "value",
                }
            }
        }
        updated_dr = dr_factory.update_dr(dr, updates)

        assert updated_dr["data"]["user_preferences"]["theme"] == "dark"
        assert updated_dr["data"]["user_preferences"]["language"] == "en"
        assert updated_dr["data"]["user_preferences"]["new_setting"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
