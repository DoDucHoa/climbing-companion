import pytest
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.virtualization.digital_replica.dr_factory import DRFactory
from src.virtualization.digital_replica.schema_registry import SchemaRegistry


class TestDevicePairingSchema:
    """Test suite for device_pairing_schema.yaml"""

    @pytest.fixture
    def dr_factory(self):
        """Create DRFactory instance with device_pairing schema"""
        schema_path = os.path.join("config", "device_pairing_schema.yaml")
        return DRFactory(schema_path)

    @pytest.fixture
    def schema_registry(self):
        """Create SchemaRegistry instance with device_pairing schema"""
        registry = SchemaRegistry()
        schema_path = os.path.join("config", "device_pairing_schema.yaml")
        registry.load_schema("device_pairing", schema_path)
        return registry

    def test_schema_loading(self, dr_factory):
        """Test that device_pairing schema loads correctly"""
        assert dr_factory.schema is not None
        assert "schemas" in dr_factory.schema
        assert "common_fields" in dr_factory.schema["schemas"]
        assert "entity" in dr_factory.schema["schemas"]
        assert "validations" in dr_factory.schema["schemas"]

    def test_create_pairing_with_minimal_data(self, dr_factory):
        """Test creating device pairing with only mandatory fields"""
        paired_time = datetime.utcnow()
        initial_data = {
            "profile": {"paired_at": paired_time},
            "data": {"user_id": "user-123", "device_id": "device-456"},
        }

        dr = dr_factory.create_dr("device_pairing", initial_data)

        # Check basic structure
        assert dr["_id"] is not None
        assert dr["type"] == "device_pairing"
        assert dr["profile"]["paired_at"] == paired_time
        assert dr["data"]["user_id"] == "user-123"
        assert dr["data"]["device_id"] == "device-456"

        # Check initialization defaults
        assert dr["data"]["pairing_status"] == "active"
        assert dr["data"]["pairing_method"] == "wifi"

        # Check metadata
        assert "created_at" in dr["metadata"]
        assert "updated_at" in dr["metadata"]
        assert isinstance(dr["metadata"]["created_at"], datetime)

    def test_create_pairing_with_complete_data(self, dr_factory):
        """Test creating device pairing with all fields"""
        paired_time = datetime.utcnow()
        unpaired_time = datetime.utcnow()

        initial_data = {
            "profile": {"paired_at": paired_time},
            "data": {
                "user_id": "user-789",
                "device_id": "device-012",
                "unpaired_at": unpaired_time,
                "pairing_status": "suspended",
                "pairing_method": "bluetooth",
            },
        }

        dr = dr_factory.create_dr("device_pairing", initial_data)

        assert dr["profile"]["paired_at"] == paired_time
        assert dr["data"]["user_id"] == "user-789"
        assert dr["data"]["device_id"] == "device-012"
        assert dr["data"]["unpaired_at"] == unpaired_time
        assert dr["data"]["pairing_status"] == "suspended"
        assert dr["data"]["pairing_method"] == "bluetooth"

    def test_pairing_status_enum_validation(self, dr_factory):
        """Test that pairing_status field validates enum values"""
        # Valid statuses
        valid_statuses = ["active", "unpaired", "suspended", "expired"]
        for status in valid_statuses:
            initial_data = {
                "profile": {"paired_at": datetime.utcnow()},
                "data": {
                    "user_id": "user-001",
                    "device_id": "device-001",
                    "pairing_status": status,
                },
            }
            dr = dr_factory.create_dr("device_pairing", initial_data)
            assert dr["data"]["pairing_status"] == status

        # Invalid status should raise error
        with pytest.raises(ValueError) as exc_info:
            initial_data = {
                "profile": {"paired_at": datetime.utcnow()},
                "data": {
                    "user_id": "user-002",
                    "device_id": "device-002",
                    "pairing_status": "invalid_status",
                },
            }
            dr_factory.create_dr("device_pairing", initial_data)
        assert "must be one of" in str(exc_info.value)

    def test_pairing_method_enum_validation(self, dr_factory):
        """Test that pairing_method field validates enum values"""
        # Valid methods
        valid_methods = ["wifi", "bluetooth", "qr_code", "nfc", "manual"]
        for method in valid_methods:
            initial_data = {
                "profile": {"paired_at": datetime.utcnow()},
                "data": {
                    "user_id": "user-003",
                    "device_id": "device-003",
                    "pairing_method": method,
                },
            }
            dr = dr_factory.create_dr("device_pairing", initial_data)
            assert dr["data"]["pairing_method"] == method

        # Invalid method should raise error
        with pytest.raises(ValueError) as exc_info:
            initial_data = {
                "profile": {"paired_at": datetime.utcnow()},
                "data": {
                    "user_id": "user-004",
                    "device_id": "device-004",
                    "pairing_method": "invalid_method",
                },
            }
            dr_factory.create_dr("device_pairing", initial_data)
        assert "must be one of" in str(exc_info.value)

    def test_missing_mandatory_fields(self, dr_factory):
        """Test that missing mandatory fields raise errors"""
        # Missing paired_at in profile
        with pytest.raises(ValueError):
            dr_factory.create_dr(
                "device_pairing",
                {
                    "profile": {},
                    "data": {"user_id": "user-005", "device_id": "device-005"},
                },
            )

        # Note: user_id and device_id in data section are optional in Pydantic validation
        # but can still be validated at the application level if needed

    def test_update_pairing(self, dr_factory):
        """Test updating device pairing DR"""
        # Create initial pairing
        initial_data = {
            "profile": {"paired_at": datetime.utcnow()},
            "data": {"user_id": "user-008", "device_id": "device-008"},
        }
        dr = dr_factory.create_dr("device_pairing", initial_data)

        # Update status and add unpaired_at
        unpaired_time = datetime.utcnow()
        updates = {"data": {"pairing_status": "unpaired", "unpaired_at": unpaired_time}}
        updated_dr = dr_factory.update_dr(dr, updates)

        assert updated_dr["data"]["pairing_status"] == "unpaired"
        assert updated_dr["data"]["unpaired_at"] == unpaired_time
        assert updated_dr["metadata"]["updated_at"] > dr["metadata"]["updated_at"]

    def test_update_with_invalid_data(self, dr_factory):
        """Test that updates validate constraints"""
        # Create initial pairing
        initial_data = {
            "profile": {"paired_at": datetime.utcnow()},
            "data": {"user_id": "user-009", "device_id": "device-009"},
        }
        dr = dr_factory.create_dr("device_pairing", initial_data)

        # Try to update with invalid status
        with pytest.raises(ValueError):
            updates = {"data": {"pairing_status": "invalid"}}
            dr_factory.update_dr(dr, updates)

        # Try to update with invalid method
        with pytest.raises(ValueError):
            updates = {"data": {"pairing_method": "teleportation"}}
            dr_factory.update_dr(dr, updates)

    def test_schema_registry_conversion(self, schema_registry):
        """Test SchemaRegistry MongoDB schema conversion"""
        validation_schema = schema_registry.get_validation_schema("device_pairing")

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
        collection_name = schema_registry.get_collection_name("device_pairing")
        assert collection_name == "device_pairing_collection"

    def test_pairing_lifecycle(self, dr_factory):
        """Test complete pairing lifecycle: active -> suspended -> unpaired"""
        # Create active pairing
        paired_time = datetime.utcnow()
        initial_data = {
            "profile": {"paired_at": paired_time},
            "data": {
                "user_id": "user-010",
                "device_id": "device-010",
                "pairing_status": "active",
                "pairing_method": "qr_code",
            },
        }
        dr = dr_factory.create_dr("device_pairing", initial_data)
        assert dr["data"]["pairing_status"] == "active"

        # Suspend pairing
        dr = dr_factory.update_dr(dr, {"data": {"pairing_status": "suspended"}})
        assert dr["data"]["pairing_status"] == "suspended"

        # Unpair
        unpaired_time = datetime.utcnow()
        dr = dr_factory.update_dr(
            dr, {"data": {"pairing_status": "unpaired", "unpaired_at": unpaired_time}}
        )
        assert dr["data"]["pairing_status"] == "unpaired"
        assert dr["data"]["unpaired_at"] == unpaired_time

    def test_different_pairing_methods(self, dr_factory):
        """Test creating pairings with different methods"""
        methods = ["wifi", "bluetooth", "qr_code", "nfc", "manual"]

        for idx, method in enumerate(methods):
            initial_data = {
                "profile": {"paired_at": datetime.utcnow()},
                "data": {
                    "user_id": f"user-{idx}",
                    "device_id": f"device-{idx}",
                    "pairing_method": method,
                },
            }
            dr = dr_factory.create_dr("device_pairing", initial_data)
            assert dr["data"]["pairing_method"] == method

    def test_datetime_fields(self, dr_factory):
        """Test datetime field handling"""
        paired_time = datetime.utcnow()
        unpaired_time = datetime.utcnow()

        initial_data = {
            "profile": {"paired_at": paired_time},
            "data": {
                "user_id": "user-011",
                "device_id": "device-011",
                "unpaired_at": unpaired_time,
            },
        }

        dr = dr_factory.create_dr("device_pairing", initial_data)

        assert dr["profile"]["paired_at"] == paired_time
        assert dr["data"]["unpaired_at"] == unpaired_time
        assert isinstance(dr["metadata"]["created_at"], datetime)
        assert isinstance(dr["metadata"]["updated_at"], datetime)

    def test_multiple_pairings_same_user(self, dr_factory):
        """Test that same user can have multiple device pairings"""
        user_id = "user-multi"

        # Create multiple pairings for same user
        for i in range(3):
            initial_data = {
                "profile": {"paired_at": datetime.utcnow()},
                "data": {
                    "user_id": user_id,
                    "device_id": f"device-{i}",
                    "pairing_method": ["wifi", "bluetooth", "nfc"][i],
                },
            }
            dr = dr_factory.create_dr("device_pairing", initial_data)
            assert dr["data"]["user_id"] == user_id
            assert dr["data"]["device_id"] == f"device-{i}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
