# Climbing Companion - Digital Twin IoT Platform

A comprehensive Digital Twin framework for IoT-enabled climbing safety monitoring, built with Flask, MongoDB, and MQTT. This system manages real-time device data, emergency alerting via Telegram, and climbing session tracking.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                         │
│         (Flask REST APIs + Web Interface)                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                Digital Twin Layer                           │
│      (DigitalTwin + DTFactory - Orchestration)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  Services Layer                             │
│  (MQTT, Telegram, Database, Analytics - Business Logic)     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Virtualization Layer                           │
│    (Digital Replicas with Schema Validation)                │
└─────────────────────────────────────────────────────────────┘
```

### Core Design Pattern: Inversion of Control

Components are initialized in `app.py` in dependency order:
1. **SchemaRegistry** → Load all YAML schemas
2. **DatabaseService** → MongoDB connection with schema validation
3. **DTFactory** → Digital Twin orchestrator
4. **DRFactory instances** → One per entity type (user, device, etc.)
5. **MQTTService & TelegramService** → IoT communication
6. **Flask blueprints** → REST API endpoints

All components stored in `app.config` for cross-request access.

## 📦 Entity Types (Digital Replicas)

The system manages six types of schema-validated entities:

| Entity Type           | Description                       | Collection Name                |
| --------------------- | --------------------------------- | ------------------------------ |
| **user**              | User accounts with authentication | `user_collection`              |
| **device**            | IoT devices                       | `device_collection`            |
| **device_pairing**    | Device-user relationships         | `device_pairing_collection`    |
| **emergency_contact** | Emergency contacts per user       | `emergency_contact_collection` |
| **climbing_session**  | Complete session records          | `climbing_session_collection`  |
| **session_event**     | Real-time session events          | `session_event_collection`     |

### Entity Schema Structure

All entities follow this pattern (defined in YAML):

```yaml
common_fields:
  profile:      # Common identification fields
    - name, email, phone, etc.
  metadata:     # System timestamps
    - created_at, updated_at

entity:
  data:         # Entity-specific fields
    - Custom fields per entity type

validations:
  mandatory_fields:   # Required fields
  type_constraints:   # Patterns, enums, min/max
  initialization:     # Default values
```

## 🔑 Key Components

### Digital Twin vs Digital Replica

- **Digital Replica (DR)**: Schema-validated representation of a physical/logical entity stored in MongoDB. Created via `DRFactory` with Pydantic validation.

- **Digital Twin (DT)**: Orchestrator that aggregates multiple DRs and manages attached services. Lives in `digital_twins` collection.

### Two-Stage Validation System

1. **Pydantic validation** (DRFactory): Dynamic model creation from YAML schemas. Validates on DR creation.
2. **MongoDB schema validation** (SchemaRegistry): Converts YAML to `$jsonSchema` for database-level enforcement.

### Services Architecture

All services extend `BaseService` and implement:

```python
def execute(self, data: Dict, dr_type: str = None, attribute: str = None) -> Any:
    # Process data and return results
    pass
```

**Available Services:**
- **DatabaseService**: MongoDB CRUD operations with schema validation
- **MQTTService**: Device communication (HiveMQ broker)
- **TelegramService**: Emergency notifications and bot interactions
- **AggregationService**: Analytics on climbing data

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- MongoDB (local or cloud - Digital Ocean configured)
- MQTT Broker (HiveMQ public broker by default)
- Telegram Bot Token (for alerts)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/DoDucHoa/climbing-companion.git
   cd climbing-companion
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure database** (`config/database.yaml`):
   ```yaml
   database:
     connection_string: "mongodb+srv://..."  # Your MongoDB URI
     settings:
       name: "climbing-companion"
   ```

4. **Configure Telegram** (`config/telegram_config.yaml`):
   ```yaml
   telegram:
     bot_token: "YOUR_BOT_TOKEN"
   ```

5. **Configure MQTT** (`config/mqtt_config.yaml`):
   ```yaml
   mqtt:
     broker:
       host: "broker.hivemq.com"
       port: 1883
   ```

### Running the Application

```bash
python app.py
```

Server starts on `http://0.0.0.0:5000` with debug mode enabled.

### First Steps

1. **Register an account**: Navigate to `http://localhost:5000/register`
2. **Login**: Use your credentials to access the dashboard
3. **Register a device**: Add an IoT device using its serial number
4. **Add emergency contacts**: Configure who receives alerts

## 📡 MQTT Device Integration

### Topics Structure

```
climbing/{device_serial}/status     # Device status updates
device/data/{device_id}            # Real-time sensor data
device/alerts/{device_id}          # Emergency alerts
```

### Example Device Payload

```json
{
  "session_id": "uuid-here",
  "user_id": "user-uuid",
  "device_serial": "ESP32-001",
  "session_state": "START",
  "temp": 22.5,
  "humidity": 45.3,
  "start_alt": 1500,
  "latitude": 46.5,
  "longitude": 11.3,
  "timestamp": "2025-12-28T10:00:00Z"
}
```

### Session States

- **START**: Session begins, creates climbing_session DR
- **ACTIVE**: Ongoing session, records session_events
- **INCIDENT**: Emergency detected, triggers Telegram alerts
- **END**: Session completes, updates final statistics

## 🔌 API Endpoints

### Authentication
- `POST /register` - Register new user
- `POST /login` - User login
- `GET /home` - User dashboard

### Digital Twins
- `POST /api/dt/` - Create Digital Twin
- `GET /api/dt/<dt_id>` - Get Digital Twin details
- `GET /api/dt/` - List all Digital Twins
- `POST /api/dt/<dt_id>/services` - Add service to DT

### Digital Replicas
- `POST /api/dr/<dr_type>` - Create Digital Replica
- `GET /api/dr/<dr_type>/<dr_id>` - Get Digital Replica
- `PUT /api/dr/<dr_type>/<dr_id>` - Update Digital Replica
- `DELETE /api/dr/<dr_type>/<dr_id>` - Delete Digital Replica
- `GET /api/dr/<dr_type>` - Query Digital Replicas

### Device Management
- `POST /register-device` - Register new device
- `POST /api/device/<device_serial>/pair` - Pair device with user
- `GET /api/devices` - List user's devices

### Emergency Contacts
- `POST /api/emergency-contacts` - Add emergency contact
- `GET /api/emergency-contacts` - List contacts
- `PUT /api/emergency-contacts/<contact_id>` - Update contact
- `DELETE /api/emergency-contacts/<contact_id>` - Remove contact

### Digital Twin Management
- `POST /api/dt-management/<dt_id>/dr` - Add DR to DT
- `DELETE /api/dt-management/<dt_id>/dr` - Remove DR from DT
- `GET /api/dt-management/<dt_id>/full` - Get full DT with DRs

## 📂 Project Structure

```
├── app.py                          # Main Flask application
├── config/
│   ├── database.yaml               # MongoDB configuration
│   ├── mqtt_config.yaml           # MQTT broker settings
│   ├── telegram_config.yaml       # Telegram bot configuration
│   ├── user_schema.yaml           # User entity schema
│   ├── device_schema.yaml         # Device entity schema
│   ├── device_pairing_schema.yaml # Pairing schema
│   ├── emergency_contact_schema.yaml
│   ├── climbing_session_schema.yaml
│   └── session_event_schema.yaml
├── src/
│   ├── application/
│   │   ├── api.py                 # Blueprint registration
│   │   ├── auth_routes.py         # Authentication endpoints
│   │   ├── base.py                # Base application class
│   │   └── routes/
│   │       ├── dt_routes.py       # Digital Twin endpoints
│   │       ├── dr_routes.py       # Digital Replica endpoints
│   │       ├── device_routes.py   # Device management
│   │       ├── dt_management_routes.py
│   │       └── emergency_contact_routes.py
│   ├── digital_twin/
│   │   ├── core.py                # DigitalTwin class
│   │   └── dt_factory.py          # DT factory and management
│   ├── services/
│   │   ├── base.py                # BaseService abstract class
│   │   ├── database_service.py    # MongoDB operations
│   │   ├── mqtt_service.py        # MQTT device communication
│   │   ├── telegram_service.py    # Telegram bot and alerts
│   │   └── analytics.py           # Data aggregation services
│   └── virtualization/
│       ├── digital_replica/
│       │   ├── dr_factory.py      # DR creation with Pydantic
│       │   └── schema_registry.py # Schema management
│       └── registry.py
├── templates/                      # HTML templates
│   ├── login.html
│   ├── register.html
│   └── home.html
├── static/                         # CSS and assets
├── tests/                          # Test suite
└── docs/                           # Documentation
```

## 🔧 Development Patterns

### Adding a New Entity Type

1. **Create YAML schema** in `config/`:
   ```yaml
   schemas:
     common_fields:
       profile: {...}
       metadata: {...}
     entity:
       data: {...}
     validations: {...}
   ```

2. **Load schema in `app.py`**:
   ```python
   schema_registry.load_schema("my_entity", "config/my_entity_schema.yaml")
   my_entity_dr_factory = DRFactory("config/my_entity_schema.yaml")
   app.config["MY_ENTITY_DR_FACTORY"] = my_entity_dr_factory
   ```

3. **Create routes blueprint** in `src/application/routes/`:
   ```python
   my_entity_api = Blueprint("my_entity_api", __name__)
   # Add endpoints...
   ```

4. **Register blueprint** in `api.py`:
   ```python
   app.register_blueprint(my_entity_api)
   ```

### Adding a New Service

1. **Extend BaseService**:
   ```python
   from src.services.base import BaseService

   class MyService(BaseService):
       def execute(self, data: Dict, dr_type: str = None, attribute: str = None):
           # Process data
           return results
   ```

2. **Register in DTFactory** (`_get_service_module_mapping()`):
   ```python
   return {
       "MyService": "src.services.my_service",
       ...
   }
   ```

3. **Attach to DT**:
   ```python
   dt.add_service(MyService())
   result = dt.execute_service("MyService", dr_type="user")
   ```

## 🔐 Security Notes

⚠️ **Current Implementation (Demo/Educational):**
- Passwords stored in plain text
- No JWT/session encryption
- Basic authentication only
- No rate limiting

## 📚 Additional Resources

- [Pairing Device Guide](docs/Pairing%20Device%20Guide.md) - Detailed device setup
- MongoDB Schema Validation: [Official Docs](https://www.mongodb.com/docs/manual/core/schema-validation/)
- Pydantic: [Official Docs](https://docs.pydantic.dev/)
- Flask Blueprints: [Official Docs](https://flask.palletsprojects.com/en/latest/blueprints/)

## 🐛 Troubleshooting

### MQTT Connection Issues
- Verify broker configuration in `config/mqtt_config.yaml`
- Check if port 1883 is open
- Review logs for connection errors

### Database Connection Errors
- Confirm MongoDB URI in `config/database.yaml`
- Test connection string with MongoDB Compass
- Check network/firewall settings

### Telegram Not Working
- Verify bot token in `config/telegram_config.yaml`
- Ensure bot is started (send `/start` command)
- Check emergency contacts have `telegram_chat_id`

### Schema Validation Failures
- Check YAML syntax in schema files
- Verify mandatory fields are provided
- Review Pydantic validation errors in logs

## 👥 Support

For issues or questions:
1. Check existing documentation in `docs/`
2. Review test files for usage examples
3. Check Flask application logs
4. Contact course instructor

---

**Built with:** Flask 3.1.0 | MongoDB | Pydantic | MQTT | Telegram Bot API