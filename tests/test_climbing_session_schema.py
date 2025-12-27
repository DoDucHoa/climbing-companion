import pytest
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.virtualization.digital_replica.dr_factory import DRFactory
from src.virtualization.digital_replica.schema_registry import SchemaRegistry


class TestClimbingSessionSchema:
    """Test suite for climbing_session_schema.yaml"""

    @pytest.fixture
    def dr_factory(self):
        """Create DRFactory instance with climbing_session schema"""
        schema_path = os.path.join("config", "climbing_session_schema.yaml")
        return DRFactory(schema_path)

    @pytest.fixture
    def schema_registry(self):
        """Create SchemaRegistry instance with climbing_session schema"""
        registry = SchemaRegistry()
        schema_path = os.path.join("config", "climbing_session_schema.yaml")
        registry.load_schema("climbing_session", schema_path)
        return registry

    def test_schema_loading(self, dr_factory):
        """Test that climbing_session schema loads correctly"""
        assert dr_factory.schema is not None
        assert "schemas" in dr_factory.schema
        assert "common_fields" in dr_factory.schema["schemas"]
        assert "entity" in dr_factory.schema["schemas"]
        assert "validations" in dr_factory.schema["schemas"]

    def test_create_session_with_minimal_data(self, dr_factory):
        """Test creating climbing session with only mandatory fields"""
        start_time = datetime.utcnow()
        initial_data = {
            "profile": {"start_at": start_time, "session_state": "START"},
            "data": {"user_id": "user-001"},
        }

        dr = dr_factory.create_dr("climbing_session", initial_data)

        # Check basic structure
        assert dr["_id"] is not None
        assert dr["type"] == "climbing_session"
        assert dr["profile"]["start_at"] == start_time
        assert dr["profile"]["session_state"] == "START"
        assert dr["data"]["user_id"] == "user-001"

        # Note: session_state is in profile, not in data for this test
        # The initialization default only applies when creating a DR without providing the field

        # Check metadata
        assert "created_at" in dr["metadata"]
        assert "updated_at" in dr["metadata"]
        assert isinstance(dr["metadata"]["created_at"], datetime)

    def test_create_session_with_complete_data(self, dr_factory):
        """Test creating climbing session with all fields"""
        start_time = datetime.utcnow()
        end_time = datetime.utcnow()

        initial_data = {
            "profile": {"start_at": start_time, "session_state": "END"},
            "data": {
                "user_id": "user-002",
                "device_id": "device-001",
                "temp": 22.5,
                "humidity": 65.0,
                "start_alt": 1000.0,
                "end_alt": 2500.0,
                "latitude": 45.5,
                "longitude": 12.3,
                "end_at": end_time,
            },
        }

        dr = dr_factory.create_dr("climbing_session", initial_data)

        assert dr["profile"]["start_at"] == start_time
        assert dr["profile"]["session_state"] == "END"
        assert dr["data"]["user_id"] == "user-002"
        assert dr["data"]["device_id"] == "device-001"
        assert dr["data"]["temp"] == 22.5
        assert dr["data"]["humidity"] == 65.0
        assert dr["data"]["start_alt"] == 1000.0
        assert dr["data"]["end_alt"] == 2500.0
        assert dr["data"]["latitude"] == 45.5
        assert dr["data"]["longitude"] == 12.3
        assert dr["data"]["end_at"] == end_time

    def test_session_state_enum_validation(self, dr_factory):
        """Test that session_state field validates enum values"""
        # Valid states
        valid_states = ["START", "ACTIVE", "END", "INCIDENT"]
        for state in valid_states:
            initial_data = {
                "profile": {"start_at": datetime.utcnow(), "session_state": state},
                "data": {"user_id": "user-003"},
            }
            dr = dr_factory.create_dr("climbing_session", initial_data)
            assert dr["profile"]["session_state"] == state

        # Invalid state should raise error
        with pytest.raises(ValueError) as exc_info:
            initial_data = {
                "profile": {
                    "start_at": datetime.utcnow(),
                    "session_state": "INVALID_STATE",
                },
                "data": {"user_id": "user-004"},
            }
            dr_factory.create_dr("climbing_session", initial_data)
        assert "must be one of" in str(exc_info.value)

    def test_latitude_constraints(self, dr_factory):
        """Test latitude min/max constraints"""
        # Valid latitudes
        for lat in [-90, -45.5, 0, 45.5, 90]:
            initial_data = {
                "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
                "data": {"user_id": "user-005", "latitude": lat},
            }
            dr = dr_factory.create_dr("climbing_session", initial_data)
            assert dr["data"]["latitude"] == lat

        # Latitude below min
        with pytest.raises(ValueError):
            initial_data = {
                "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
                "data": {"user_id": "user-006", "latitude": -91},
            }
            dr_factory.create_dr("climbing_session", initial_data)

        # Latitude above max
        with pytest.raises(ValueError):
            initial_data = {
                "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
                "data": {"user_id": "user-007", "latitude": 91},
            }
            dr_factory.create_dr("climbing_session", initial_data)

    def test_longitude_constraints(self, dr_factory):
        """Test longitude min/max constraints"""
        # Valid longitudes
        for lon in [-180, -90, 0, 90, 180]:
            initial_data = {
                "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
                "data": {"user_id": "user-008", "longitude": lon},
            }
            dr = dr_factory.create_dr("climbing_session", initial_data)
            assert dr["data"]["longitude"] == lon

        # Longitude below min
        with pytest.raises(ValueError):
            initial_data = {
                "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
                "data": {"user_id": "user-009", "longitude": -181},
            }
            dr_factory.create_dr("climbing_session", initial_data)

        # Longitude above max
        with pytest.raises(ValueError):
            initial_data = {
                "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
                "data": {"user_id": "user-010", "longitude": 181},
            }
            dr_factory.create_dr("climbing_session", initial_data)

    def test_missing_mandatory_fields(self, dr_factory):
        """Test that missing mandatory fields raise errors"""
        # Missing start_at in profile
        with pytest.raises(ValueError):
            dr_factory.create_dr(
                "climbing_session",
                {
                    "profile": {"session_state": "ACTIVE"},
                    "data": {"user_id": "user-011"},
                },
            )

        # Missing session_state in profile
        with pytest.raises(ValueError):
            dr_factory.create_dr(
                "climbing_session",
                {
                    "profile": {"start_at": datetime.utcnow()},
                    "data": {"user_id": "user-012"},
                },
            )

        # Note: user_id in data section is optional in Pydantic validation
        # but can still be validated at the application level if needed

    def test_update_session(self, dr_factory):
        """Test updating climbing session DR"""
        # Create initial session
        initial_data = {
            "profile": {"start_at": datetime.utcnow(), "session_state": "START"},
            "data": {"user_id": "user-013", "start_alt": 1000.0},
        }
        dr = dr_factory.create_dr("climbing_session", initial_data)

        # Update session state and altitude
        end_time = datetime.utcnow()
        updates = {
            "profile": {"session_state": "END"},
            "data": {"end_alt": 2000.0, "end_at": end_time},
        }
        updated_dr = dr_factory.update_dr(dr, updates)

        assert updated_dr["profile"]["session_state"] == "END"
        assert updated_dr["data"]["end_alt"] == 2000.0
        assert updated_dr["data"]["end_at"] == end_time
        assert updated_dr["metadata"]["updated_at"] > dr["metadata"]["updated_at"]

    def test_update_with_invalid_data(self, dr_factory):
        """Test that updates validate constraints"""
        # Create initial session
        initial_data = {
            "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
            "data": {"user_id": "user-014"},
        }
        dr = dr_factory.create_dr("climbing_session", initial_data)

        # Try to update with invalid session_state
        with pytest.raises(ValueError):
            updates = {"profile": {"session_state": "PAUSED"}}
            dr_factory.update_dr(dr, updates)

        # Try to update with invalid latitude
        with pytest.raises(ValueError):
            updates = {"data": {"latitude": 100}}
            dr_factory.update_dr(dr, updates)

        # Try to update with invalid longitude
        with pytest.raises(ValueError):
            updates = {"data": {"longitude": -200}}
            dr_factory.update_dr(dr, updates)

    def test_schema_registry_conversion(self, schema_registry):
        """Test SchemaRegistry MongoDB schema conversion"""
        validation_schema = schema_registry.get_validation_schema("climbing_session")

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
        collection_name = schema_registry.get_collection_name("climbing_session")
        assert collection_name == "climbing_session_collection"

    def test_session_lifecycle(self, dr_factory):
        """Test complete session lifecycle: START -> ACTIVE -> END"""
        # Create session in START state
        start_time = datetime.utcnow()
        initial_data = {
            "profile": {"start_at": start_time, "session_state": "START"},
            "data": {"user_id": "user-015", "start_alt": 500.0},
        }
        dr = dr_factory.create_dr("climbing_session", initial_data)
        assert dr["profile"]["session_state"] == "START"

        # Transition to ACTIVE
        dr = dr_factory.update_dr(dr, {"profile": {"session_state": "ACTIVE"}})
        assert dr["profile"]["session_state"] == "ACTIVE"

        # End session
        end_time = datetime.utcnow()
        dr = dr_factory.update_dr(
            dr, {"profile": {"session_state": "END"}, "data": {"end_at": end_time}}
        )
        assert dr["profile"]["session_state"] == "END"
        assert dr["data"]["end_at"] == end_time

    def test_incident_handling(self, dr_factory):
        """Test session can transition to INCIDENT state"""
        initial_data = {
            "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
            "data": {"user_id": "user-016"},
        }
        dr = dr_factory.create_dr("climbing_session", initial_data)

        # Mark as incident
        dr = dr_factory.update_dr(dr, {"profile": {"session_state": "INCIDENT"}})
        assert dr["profile"]["session_state"] == "INCIDENT"

    def test_environmental_data(self, dr_factory):
        """Test temperature and humidity fields"""
        initial_data = {
            "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
            "data": {
                "user_id": "user-017",
                "temp": -5.5,  # Can be negative
                "humidity": 85.3,
            },
        }
        dr = dr_factory.create_dr("climbing_session", initial_data)

        assert dr["data"]["temp"] == -5.5
        assert dr["data"]["humidity"] == 85.3

    def test_altitude_tracking(self, dr_factory):
        """Test start and end altitude tracking"""
        initial_data = {
            "profile": {"start_at": datetime.utcnow(), "session_state": "ACTIVE"},
            "data": {
                "user_id": "user-018",
                "start_alt": 1500.0,
                "end_alt": 3200.5,
            },
        }
        dr = dr_factory.create_dr("climbing_session", initial_data)

        assert dr["data"]["start_alt"] == 1500.0
        assert dr["data"]["end_alt"] == 3200.5
        # Can calculate altitude gain
        altitude_gain = dr["data"]["end_alt"] - dr["data"]["start_alt"]
        assert altitude_gain == 1700.5

    def test_datetime_fields(self, dr_factory):
        """Test datetime field handling"""
        start_time = datetime.utcnow()
        end_time = datetime.utcnow()

        initial_data = {
            "profile": {"start_at": start_time, "session_state": "END"},
            "data": {"user_id": "user-019", "end_at": end_time},
        }

        dr = dr_factory.create_dr("climbing_session", initial_data)

        assert dr["profile"]["start_at"] == start_time
        assert dr["data"]["end_at"] == end_time
        assert isinstance(dr["metadata"]["created_at"], datetime)
        assert isinstance(dr["metadata"]["updated_at"], datetime)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
