import pytest
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.virtualization.digital_replica.dr_factory import DRFactory
from src.virtualization.digital_replica.schema_registry import SchemaRegistry


class TestSessionEventSchema:
    """Test suite for session_event_schema.yaml"""

    @pytest.fixture
    def dr_factory(self):
        """Create DRFactory instance with session_event schema"""
        schema_path = os.path.join("config", "session_event_schema.yaml")
        return DRFactory(schema_path)

    @pytest.fixture
    def schema_registry(self):
        """Create SchemaRegistry instance with session_event schema"""
        registry = SchemaRegistry()
        schema_path = os.path.join("config", "session_event_schema.yaml")
        registry.load_schema("session_event", schema_path)
        return registry

    def test_schema_loading(self, dr_factory):
        """Test that session_event schema loads correctly"""
        assert dr_factory.schema is not None
        assert "schemas" in dr_factory.schema
        assert "common_fields" in dr_factory.schema["schemas"]
        assert "entity" in dr_factory.schema["schemas"]
        assert "validations" in dr_factory.schema["schemas"]

    def test_create_event_with_minimal_data(self, dr_factory):
        """Test creating session event with only mandatory fields"""
        create_time = datetime.utcnow()
        initial_data = {
            "profile": {"create_at": create_time},
            "data": {"session_id": "session-001"},
        }

        dr = dr_factory.create_dr("session_event", initial_data)

        # Check basic structure
        assert dr["_id"] is not None
        assert dr["type"] == "session_event"
        assert dr["profile"]["create_at"] == create_time
        assert dr["data"]["session_id"] == "session-001"

        # Check metadata
        assert "created_at" in dr["metadata"]
        assert isinstance(dr["metadata"]["created_at"], datetime)

    def test_create_event_with_complete_data(self, dr_factory):
        """Test creating session event with all fields"""
        create_time = datetime.utcnow()
        initial_data = {
            "profile": {"create_at": create_time},
            "data": {"session_id": "session-002", "alt": 1250.5},
        }

        dr = dr_factory.create_dr("session_event", initial_data)

        assert dr["profile"]["create_at"] == create_time
        assert dr["data"]["session_id"] == "session-002"
        assert dr["data"]["alt"] == 1250.5

    def test_altitude_field_types(self, dr_factory):
        """Test that altitude field accepts different numeric types"""
        create_time = datetime.utcnow()

        # Test with integer
        initial_data = {
            "profile": {"create_at": create_time},
            "data": {"session_id": "session-003", "alt": 1500},
        }
        dr = dr_factory.create_dr("session_event", initial_data)
        assert dr["data"]["alt"] == 1500.0

        # Test with float
        initial_data = {
            "profile": {"create_at": create_time},
            "data": {"session_id": "session-004", "alt": 2345.67},
        }
        dr = dr_factory.create_dr("session_event", initial_data)
        assert dr["data"]["alt"] == 2345.67

        # Test with negative altitude (below sea level)
        initial_data = {
            "profile": {"create_at": create_time},
            "data": {"session_id": "session-005", "alt": -50.5},
        }
        dr = dr_factory.create_dr("session_event", initial_data)
        assert dr["data"]["alt"] == -50.5

    def test_missing_mandatory_fields(self, dr_factory):
        """Test that missing mandatory fields raise errors"""
        # Missing create_at in profile
        with pytest.raises(ValueError):
            dr_factory.create_dr(
                "session_event", {"profile": {}, "data": {"session_id": "session-006"}}
            )

        # Note: session_id in data section is optional in Pydantic validation
        # but can still be validated at the application level if needed

    def test_update_event(self, dr_factory):
        """Test updating session event DR"""
        # Create initial event
        initial_data = {
            "profile": {"create_at": datetime.utcnow()},
            "data": {"session_id": "session-007"},
        }
        dr = dr_factory.create_dr("session_event", initial_data)

        # Update altitude
        updates = {"data": {"alt": 3000.0}}
        updated_dr = dr_factory.update_dr(dr, updates)

        assert updated_dr["data"]["alt"] == 3000.0
        assert updated_dr["data"]["session_id"] == "session-007"
        assert updated_dr["metadata"]["created_at"] > datetime(2020, 1, 1)

    def test_update_preserves_existing_data(self, dr_factory):
        """Test that updates preserve existing data fields"""
        # Create event with altitude
        initial_data = {
            "profile": {"create_at": datetime.utcnow()},
            "data": {"session_id": "session-008", "alt": 1000.0},
        }
        dr = dr_factory.create_dr("session_event", initial_data)

        # Update only session_id
        updates = {"data": {"session_id": "session-008-updated"}}
        updated_dr = dr_factory.update_dr(dr, updates)

        assert updated_dr["data"]["session_id"] == "session-008-updated"
        assert updated_dr["data"]["alt"] == 1000.0

    def test_schema_registry_conversion(self, schema_registry):
        """Test SchemaRegistry MongoDB schema conversion"""
        validation_schema = schema_registry.get_validation_schema("session_event")

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
        collection_name = schema_registry.get_collection_name("session_event")
        assert collection_name == "session_event_collection"

    def test_datetime_field(self, dr_factory):
        """Test datetime field handling"""
        create_time = datetime.utcnow()
        initial_data = {
            "profile": {"create_at": create_time},
            "data": {"session_id": "session-009"},
        }

        dr = dr_factory.create_dr("session_event", initial_data)

        assert dr["profile"]["create_at"] == create_time
        assert isinstance(dr["metadata"]["created_at"], datetime)

    def test_multiple_events_same_session(self, dr_factory):
        """Test that same session can have multiple events"""
        session_id = "session-multi"
        create_time = datetime.utcnow()

        # Create multiple events for same session
        altitudes = [100.0, 250.5, 500.0]
        for i, alt in enumerate(altitudes):
            initial_data = {
                "profile": {"create_at": create_time},
                "data": {"session_id": session_id, "alt": alt},
            }
            dr = dr_factory.create_dr("session_event", initial_data)
            assert dr["data"]["session_id"] == session_id
            assert dr["data"]["alt"] == alt

    def test_event_without_altitude(self, dr_factory):
        """Test creating event without altitude field"""
        initial_data = {
            "profile": {"create_at": datetime.utcnow()},
            "data": {"session_id": "session-010"},
        }

        dr = dr_factory.create_dr("session_event", initial_data)

        assert dr["data"]["session_id"] == "session-010"
        assert "alt" not in dr["data"]

    def test_invalid_altitude_type(self, dr_factory):
        """Test that invalid altitude types raise errors"""
        with pytest.raises(ValueError):
            initial_data = {
                "profile": {"create_at": datetime.utcnow()},
                "data": {"session_id": "session-011", "alt": "not-a-number"},
            }
            dr_factory.create_dr("session_event", initial_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
