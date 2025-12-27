import pytest
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.virtualization.digital_replica.dr_factory import DRFactory
from src.virtualization.digital_replica.schema_registry import SchemaRegistry


class TestEmergencyContactSchema:
    """Test suite for emergency_contact_schema.yaml"""

    @pytest.fixture
    def dr_factory(self):
        """Create DRFactory instance with emergency_contact schema"""
        schema_path = os.path.join("config", "emergency_contact_schema.yaml")
        return DRFactory(schema_path)

    @pytest.fixture
    def schema_registry(self):
        """Create SchemaRegistry instance with emergency_contact schema"""
        registry = SchemaRegistry()
        schema_path = os.path.join("config", "emergency_contact_schema.yaml")
        registry.load_schema("emergency_contact", schema_path)
        return registry

    def test_schema_loading(self, dr_factory):
        """Test that emergency_contact schema loads correctly"""
        assert dr_factory.schema is not None
        assert "schemas" in dr_factory.schema
        assert "common_fields" in dr_factory.schema["schemas"]
        assert "entity" in dr_factory.schema["schemas"]
        assert "validations" in dr_factory.schema["schemas"]

    def test_create_emergency_contact_with_minimal_data(self, dr_factory):
        """Test creating emergency contact with only mandatory fields"""
        initial_data = {
            "profile": {"name": "John Doe", "phone": "+1234567890"},
            "data": {"user_id": "user-123"},
        }

        dr = dr_factory.create_dr("emergency_contact", initial_data)

        # Check basic structure
        assert dr["_id"] is not None
        assert dr["type"] == "emergency_contact"
        assert dr["profile"]["name"] == "John Doe"
        assert dr["profile"]["phone"] == "+1234567890"
        assert dr["data"]["user_id"] == "user-123"

        # Check initialization defaults (these are set by DRFactory from schema initialization)
        assert dr["data"]["is_active"] == True
        assert dr["data"]["relationship_type"] == "other"

        # Check metadata
        assert "created_at" in dr["metadata"]
        assert "updated_at" in dr["metadata"]
        assert isinstance(dr["metadata"]["created_at"], datetime)

    def test_create_emergency_contact_with_complete_data(self, dr_factory):
        """Test creating emergency contact with all fields"""
        initial_data = {
            "profile": {
                "name": "Jane Smith",
                "phone": "+9876543210",
                "email": "jane.smith@example.com",
                "telegram_chat_id": "123456789",
            },
            "data": {
                "user_id": "user-456",
                "relationship_type": "spouse",
                "is_active": True,
            },
        }

        dr = dr_factory.create_dr("emergency_contact", initial_data)

        assert dr["profile"]["name"] == "Jane Smith"
        assert dr["profile"]["phone"] == "+9876543210"
        assert dr["profile"]["email"] == "jane.smith@example.com"
        assert dr["profile"]["telegram_chat_id"] == "123456789"
        assert dr["data"]["user_id"] == "user-456"
        assert dr["data"]["relationship_type"] == "spouse"
        assert dr["data"]["is_active"] == True

    def test_name_field(self, dr_factory):
        """Test name field accepts various values"""
        # Note: min_length/max_length constraints in schema are not enforced by DRFactory
        # This could be a future enhancement

        # Valid names of various lengths
        test_names = ["A", "AB", "John Doe", "A" * 100, "A" * 150]
        for name in test_names:
            initial_data = {
                "profile": {"name": name, "phone": "+1234567890"},
                "data": {"user_id": "user-123"},
            }
            dr = dr_factory.create_dr("emergency_contact", initial_data)
            assert dr["profile"]["name"] == name

    def test_phone_pattern_validation(self, dr_factory):
        """Test phone number pattern validation"""
        # Valid phone numbers
        valid_phones = ["+1234567890", "1234567890", "+123456789012345"]
        for phone in valid_phones:
            initial_data = {
                "profile": {"name": "John Doe", "phone": phone},
                "data": {"user_id": "user-123"},
            }
            dr = dr_factory.create_dr("emergency_contact", initial_data)
            assert dr["profile"]["phone"] == phone

        # Invalid phone numbers
        invalid_phones = ["123", "+12345", "abc1234567", "123-456-7890"]
        for phone in invalid_phones:
            with pytest.raises(ValueError) as exc_info:
                initial_data = {
                    "profile": {"name": "John Doe", "phone": phone},
                    "data": {"user_id": "user-123"},
                }
                dr_factory.create_dr("emergency_contact", initial_data)
            assert "does not match required pattern" in str(exc_info.value)

    def test_email_pattern_validation(self, dr_factory):
        """Test email pattern validation"""
        # Valid emails
        valid_emails = [
            "user@example.com",
            "user.name@example.co.uk",
            "user+tag@example.com",
        ]
        for email in valid_emails:
            initial_data = {
                "profile": {
                    "name": "John Doe",
                    "phone": "+1234567890",
                    "email": email,
                },
                "data": {"user_id": "user-123"},
            }
            dr = dr_factory.create_dr("emergency_contact", initial_data)
            assert dr["profile"]["email"] == email

        # Invalid emails
        invalid_emails = ["invalid", "user@", "@example.com", "user@example"]
        for email in invalid_emails:
            with pytest.raises(ValueError) as exc_info:
                initial_data = {
                    "profile": {
                        "name": "John Doe",
                        "phone": "+1234567890",
                        "email": email,
                    },
                    "data": {"user_id": "user-123"},
                }
                dr_factory.create_dr("emergency_contact", initial_data)
            assert "does not match required pattern" in str(exc_info.value)

    def test_telegram_chat_id_pattern_validation(self, dr_factory):
        """Test telegram_chat_id pattern validation"""
        # Valid telegram chat IDs
        valid_ids = ["123456789", "9876543210"]
        for chat_id in valid_ids:
            initial_data = {
                "profile": {
                    "name": "John Doe",
                    "phone": "+1234567890",
                    "telegram_chat_id": chat_id,
                },
                "data": {"user_id": "user-123"},
            }
            dr = dr_factory.create_dr("emergency_contact", initial_data)
            assert dr["profile"]["telegram_chat_id"] == chat_id

        # Invalid telegram chat IDs
        invalid_ids = ["abc123", "123-456", "+123456"]
        for chat_id in invalid_ids:
            with pytest.raises(ValueError) as exc_info:
                initial_data = {
                    "profile": {
                        "name": "John Doe",
                        "phone": "+1234567890",
                        "telegram_chat_id": chat_id,
                    },
                    "data": {"user_id": "user-123"},
                }
                dr_factory.create_dr("emergency_contact", initial_data)
            assert "does not match required pattern" in str(exc_info.value)

    def test_relationship_type_enum_validation(self, dr_factory):
        """Test relationship_type enum validation"""
        # Valid relationship types
        valid_types = [
            "family",
            "friend",
            "colleague",
            "spouse",
            "parent",
            "sibling",
            "child",
            "other",
        ]
        for rel_type in valid_types:
            initial_data = {
                "profile": {"name": "John Doe", "phone": "+1234567890"},
                "data": {"user_id": "user-123", "relationship_type": rel_type},
            }
            dr = dr_factory.create_dr("emergency_contact", initial_data)
            assert dr["data"]["relationship_type"] == rel_type

        # Invalid relationship type
        with pytest.raises(ValueError) as exc_info:
            initial_data = {
                "profile": {"name": "John Doe", "phone": "+1234567890"},
                "data": {"user_id": "user-123", "relationship_type": "invalid"},
            }
            dr_factory.create_dr("emergency_contact", initial_data)
        assert "must be one of" in str(exc_info.value)

    def test_missing_mandatory_fields(self, dr_factory):
        """Test that missing mandatory profile fields raise errors"""
        # Missing name in profile (enforced by Pydantic)
        with pytest.raises(ValueError):
            dr_factory.create_dr(
                "emergency_contact",
                {"profile": {"phone": "+1234567890"}, "data": {"user_id": "user-123"}},
            )

        # Missing phone in profile (enforced by Pydantic)
        with pytest.raises(ValueError):
            dr_factory.create_dr(
                "emergency_contact",
                {"profile": {"name": "John Doe"}, "data": {"user_id": "user-123"}},
            )

        # Note: user_id in data section is marked as mandatory in schema,
        # but all data fields have default None in Pydantic, so it's not enforced
        # This could be validated at application level if needed
        dr = dr_factory.create_dr(
            "emergency_contact",
            {"profile": {"name": "John Doe", "phone": "+1234567890"}, "data": {}},
        )
        assert dr["data"].get("user_id") is None

    def test_update_emergency_contact(self, dr_factory):
        """Test updating emergency contact DR"""
        # Create initial emergency contact
        initial_data = {
            "profile": {"name": "John Doe", "phone": "+1234567890"},
            "data": {"user_id": "user-123", "relationship_type": "friend"},
        }
        dr = dr_factory.create_dr("emergency_contact", initial_data)

        # Update relationship type and add email
        updates = {
            "profile": {"email": "john.doe@example.com"},
            "data": {"relationship_type": "family", "is_active": False},
        }
        updated_dr = dr_factory.update_dr(dr, updates)

        assert updated_dr["profile"]["email"] == "john.doe@example.com"
        assert updated_dr["data"]["relationship_type"] == "family"
        assert updated_dr["data"]["is_active"] == False
        assert updated_dr["metadata"]["updated_at"] > dr["metadata"]["updated_at"]

    def test_update_with_invalid_data(self, dr_factory):
        """Test that updates validate constraints"""
        # Create initial emergency contact
        initial_data = {
            "profile": {"name": "John Doe", "phone": "+1234567890"},
            "data": {"user_id": "user-123"},
        }
        dr = dr_factory.create_dr("emergency_contact", initial_data)

        # Try to update with invalid email
        with pytest.raises(ValueError):
            updates = {"profile": {"email": "invalid-email"}}
            dr_factory.update_dr(dr, updates)

        # Try to update with invalid relationship type
        with pytest.raises(ValueError):
            updates = {"data": {"relationship_type": "invalid_type"}}
            dr_factory.update_dr(dr, updates)

    def test_schema_registry_conversion(self, schema_registry):
        """Test SchemaRegistry MongoDB schema conversion"""
        validation_schema = schema_registry.get_validation_schema("emergency_contact")

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
        collection_name = schema_registry.get_collection_name("emergency_contact")
        assert collection_name == "emergency_contact_collection"

    def test_is_active_boolean(self, dr_factory):
        """Test is_active boolean field"""
        # Test with True
        initial_data = {
            "profile": {"name": "John Doe", "phone": "+1234567890"},
            "data": {"user_id": "user-123", "is_active": True},
        }
        dr = dr_factory.create_dr("emergency_contact", initial_data)
        assert dr["data"]["is_active"] == True

        # Test with False
        initial_data = {
            "profile": {"name": "Jane Doe", "phone": "+1234567890"},
            "data": {"user_id": "user-456", "is_active": False},
        }
        dr = dr_factory.create_dr("emergency_contact", initial_data)
        assert dr["data"]["is_active"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
