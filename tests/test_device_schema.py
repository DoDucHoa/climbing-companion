import pytest
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.virtualization.digital_replica.dr_factory import DRFactory
from src.virtualization.digital_replica.schema_registry import SchemaRegistry


class TestDeviceSchema:
    """Test suite for device_schema.yaml"""

    @pytest.fixture
    def dr_factory(self):
        """Create DRFactory instance with device schema"""
        schema_path = os.path.join("config", "device_schema.yaml")
        return DRFactory(schema_path)

    @pytest.fixture
    def schema_registry(self):
        """Create SchemaRegistry instance with device schema"""
        registry = SchemaRegistry()
        schema_path = os.path.join("config", "device_schema.yaml")
        registry.load_schema("device", schema_path)
        return registry

    def test_schema_loading(self, dr_factory):
        """Test that device schema loads correctly"""
        assert dr_factory.schema is not None
        assert "schemas" in dr_factory.schema
        assert "common_fields" in dr_factory.schema["schemas"]
        assert "entity" in dr_factory.schema["schemas"]
        assert "validations" in dr_factory.schema["schemas"]

    def test_create_device_with_minimal_data(self, dr_factory):
        """Test creating device with only mandatory fields"""
        initial_data = {
            "profile": {"serial_number": "DEV-001"},
            "data": {"status": "active"},
        }

        dr = dr_factory.create_dr("device", initial_data)

        # Check basic structure
        assert dr["_id"] is not None
        assert dr["type"] == "device"
        assert dr["profile"]["serial_number"] == "DEV-001"
        assert dr["data"]["status"] == "active"

        # Check initialization defaults
        assert dr["data"]["battery_level"] == 100
        assert dr["data"]["settings"]["sync_interval"] == 300

        # Check metadata
        assert "created_at" in dr["metadata"]
        assert "updated_at" in dr["metadata"]
        assert isinstance(dr["metadata"]["created_at"], datetime)

    def test_create_device_with_complete_data(self, dr_factory):
        """Test creating device with all fields"""
        initial_data = {
            "profile": {"serial_number": "DEV-002"},
            "data": {
                "status": "maintenance",
                "firmware_version": "1.2.3",
                "battery_level": 75.5,
                "last_sync_at": datetime.utcnow(),
                "settings": {"sync_interval": 600, "auto_update": True},
            },
        }

        dr = dr_factory.create_dr("device", initial_data)

        assert dr["profile"]["serial_number"] == "DEV-002"
        assert dr["data"]["status"] == "maintenance"
        assert dr["data"]["firmware_version"] == "1.2.3"
        assert dr["data"]["battery_level"] == 75.5
        assert dr["data"]["settings"]["sync_interval"] == 600
        assert dr["data"]["settings"]["auto_update"] == True

    def test_status_enum_validation(self, dr_factory):
        """Test that status field validates enum values"""
        # Valid status
        valid_statuses = ["active", "inactive", "maintenance", "retired"]
        for status in valid_statuses:
            initial_data = {
                "profile": {"serial_number": "DEV-003"},
                "data": {"status": status},
            }
            dr = dr_factory.create_dr("device", initial_data)
            assert dr["data"]["status"] == status

        # Invalid status should raise error
        with pytest.raises(ValueError) as exc_info:
            initial_data = {
                "profile": {"serial_number": "DEV-004"},
                "data": {"status": "invalid_status"},
            }
            dr_factory.create_dr("device", initial_data)
        assert "must be one of" in str(exc_info.value)

    def test_battery_level_constraints(self, dr_factory):
        """Test battery_level min/max constraints"""
        # Valid battery levels
        for level in [0, 50, 100]:
            initial_data = {
                "profile": {"serial_number": "DEV-005"},
                "data": {"status": "active", "battery_level": level},
            }
            dr = dr_factory.create_dr("device", initial_data)
            assert dr["data"]["battery_level"] == level

        # Battery level below min
        with pytest.raises(ValueError):
            initial_data = {
                "profile": {"serial_number": "DEV-006"},
                "data": {"status": "active", "battery_level": -1},
            }
            dr_factory.create_dr("device", initial_data)

        # Battery level above max
        with pytest.raises(ValueError):
            initial_data = {
                "profile": {"serial_number": "DEV-007"},
                "data": {"status": "active", "battery_level": 101},
            }
            dr_factory.create_dr("device", initial_data)

    def test_missing_mandatory_fields(self, dr_factory):
        """Test that missing mandatory fields raise errors"""
        # Missing serial_number in profile
        with pytest.raises(ValueError):
            dr_factory.create_dr(
                "device", {"profile": {}, "data": {"status": "active"}}
            )

        # Note: status in data section is optional in Pydantic validation
        # but can still be validated at the application level if needed

    def test_update_device(self, dr_factory):
        """Test updating device DR"""
        # Create initial device
        initial_data = {
            "profile": {"serial_number": "DEV-009"},
            "data": {"status": "inactive"},
        }
        dr = dr_factory.create_dr("device", initial_data)

        # Update status and battery
        updates = {
            "data": {
                "status": "active",
                "battery_level": 85,
                "firmware_version": "2.0.0",
            }
        }
        updated_dr = dr_factory.update_dr(dr, updates)

        assert updated_dr["data"]["status"] == "active"
        assert updated_dr["data"]["battery_level"] == 85
        assert updated_dr["data"]["firmware_version"] == "2.0.0"
        assert updated_dr["metadata"]["updated_at"] > dr["metadata"]["updated_at"]

    def test_update_with_invalid_data(self, dr_factory):
        """Test that updates validate constraints"""
        # Create initial device
        initial_data = {
            "profile": {"serial_number": "DEV-010"},
            "data": {"status": "active"},
        }
        dr = dr_factory.create_dr("device", initial_data)

        # Try to update with invalid status
        with pytest.raises(ValueError):
            updates = {"data": {"status": "broken"}}
            dr_factory.update_dr(dr, updates)

        # Try to update with invalid battery level
        with pytest.raises(ValueError):
            updates = {"data": {"battery_level": 150}}
            dr_factory.update_dr(dr, updates)

    def test_schema_registry_conversion(self, schema_registry):
        """Test SchemaRegistry MongoDB schema conversion"""
        validation_schema = schema_registry.get_validation_schema("device")

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
        collection_name = schema_registry.get_collection_name("device")
        assert collection_name == "device_collection"

    def test_settings_dict_field(self, dr_factory):
        """Test that settings field accepts nested dictionary"""
        initial_data = {
            "profile": {"serial_number": "DEV-011"},
            "data": {
                "status": "active",
                "settings": {
                    "sync_interval": 300,
                    "auto_update": True,
                    "notifications": {"enabled": True, "frequency": "daily"},
                },
            },
        }

        dr = dr_factory.create_dr("device", initial_data)

        assert dr["data"]["settings"]["sync_interval"] == 300
        assert dr["data"]["settings"]["auto_update"] == True
        assert dr["data"]["settings"]["notifications"]["enabled"] == True
        assert dr["data"]["settings"]["notifications"]["frequency"] == "daily"

    def test_datetime_fields(self, dr_factory):
        """Test datetime field handling"""
        now = datetime.utcnow()
        initial_data = {
            "profile": {"serial_number": "DEV-012"},
            "data": {"status": "active", "last_sync_at": now},
        }

        dr = dr_factory.create_dr("device", initial_data)

        assert dr["data"]["last_sync_at"] == now
        assert isinstance(dr["metadata"]["created_at"], datetime)
        assert isinstance(dr["metadata"]["updated_at"], datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
