# Climbing Companion - Digital Twin IoT Platform

A comprehensive Digital Twin framework for IoT-enabled climbing safety monitoring, built with Flask, MongoDB, and MQTT. This system manages device data, emergency alerting via Telegram, and climbing session tracking.

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
### Session States

- **START**: Session begins, creates climbing_session DR
- **ACTIVE**: Ongoing session, records session_events
- **INCIDENT**: Emergency detected, triggers Telegram alerts
- **END**: Session completes, updates final statistics

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

## 🔐 Security Notes

⚠️ **Current Implementation (Demo/Educational):**
- Passwords stored in plain text
- No JWT/session encryption
- Basic authentication only
- No rate limiting

## 📚 Additional Resources

- [Pairing Device Guide](docs/Pairing%20Device%20Guide.md) - Detailed device setup

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

---

**Built with:** Flask 3.1.0 | MongoDB | Pydantic | MQTT | Telegram Bot API