# Climbing Companion - Digital Twin IoT Platform

A comprehensive Digital Twin framework for IoT-enabled climbing safety monitoring, built with Flask, MongoDB, and MQTT. This system manages device data, emergency alerting via Telegram, and climbing session tracking.

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

The system uses **HiveMQ public broker** (`broker.hivemq.com:1883`) for real-time device communication. All messages use **QoS 1** for reliable delivery.

### Topic Structure

| Topic Pattern                        | Direction       | Purpose                                                |
| ------------------------------------ | --------------- | ------------------------------------------------------ |
| `climbing/{device_serial}/status`    | Device → Server | Update device pairing status                           |
| `climbing/{device_serial}/telemetry` | Device → Server | Send session data and sensor readings                  |
| `climbing/{device_serial}/telegram`  | Device → Server | Send data to emergency contact                         |
| `climbing/{device_serial}/request`   | Server → Device | Notify device that emergency contact requests for data |

**Note**: `{device_serial}` is the unique hardware identifier registered in the system.

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

- [Testing Guide](docs/Testing%20Guide.md) - Detailed testing guide


**Built with:** Flask 3.1.0 | MongoDB | Pydantic | MQTT | Telegram Bot API