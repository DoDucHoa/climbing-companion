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

## 🔧 IoT Device Implementation (NodeMCU ESP8266)

The climbing companion device is built on **ESP8266 NodeMCU** with multiple sensors for comprehensive climbing safety monitoring.

### Hardware Components

| Component       | Model/Type      | Purpose                                        |
| --------------- | --------------- | ---------------------------------------------- |
| Microcontroller | ESP8266 NodeMCU | WiFi connectivity and main processing          |
| Environmental   | BME280          | Temperature, humidity, and barometric altitude |
| Motion Sensor   | MPU9250         | 9-axis IMU for fall detection (accelerometer)  |
| GPS Module      | Generic GPS     | Location tracking (UART communication)         |
| RGB LED         | Common Anode    | Visual status indication (3 pins: R, G, B)     |
| Buzzer          | Active Buzzer   | Audio alerts for incidents                     |
| Push Button     | Momentary       | Session start/stop and incident cancellation   |

### Device State Machine

The device operates through a finite state machine with the following states:

#### 1. **INACTIVE** (Green LED)
- Default state when powered on
- Waiting for user to press button to start climbing session
- Periodic sensor readings in standby mode

#### 2. **START** (Transition State)
- Triggered by button press from INACTIVE
- Captures baseline environmental data:
  - GPS coordinates (latitude, longitude)
  - Initial barometric altitude
  - Temperature and humidity
  - Generates unique session ID
- Publishes session start message to MQTT
- Transitions to ACTIVE state

#### 3. **ACTIVE** (Red LED)
- Main climbing monitoring state
- **Altitude tracking**: Logs barometric height delta every 500ms (2Hz frequency)
- **Fall detection**: Continuously monitors accelerometer data
  - Triggers on extreme G-force (<0.25g or >6.0g)
  - Monitors for 10 seconds of stillness after trigger
  - Movement within 5-10s window cancels alarm
- Batches up to 40 altitude points before sending to server
- Button press transitions to END state

#### 4. **INCIDENT** (Blinking Yellow LED + Buzzer)
- Activated when fall detected + 10s of no movement
- **30-second local countdown**:
  - Yellow LED blinks at 1Hz
  - Buzzer beeps at 1kHz (alternating on/off)
  - Button press cancels and returns to ACTIVE
- **After 30 seconds**: Sends emergency MQTT message with:
  - Current GPS coordinates
  - Altitude at incident time
  - Session ID for tracking
- Continues altitude monitoring (fall detection disabled)

#### 5. **END** (Transition State)
- Triggered by button press from ACTIVE
- Sends any pending altitude trace data
- Captures final GPS altitude
- Publishes session end message with total duration
- Returns to INACTIVE state

### Configuration Parameters

```cpp
MONITORING_INTERVALL = 500ms      // Altitude sampling rate (2Hz)
MAX_BATCH_SIZE = 40               // Points per MQTT message (20 seconds)
INCIDENT_WAIT_TIME = 30000ms      // Local alarm duration before emergency
SEA_LEVEL_PRESSURE_HPA = 1022.0   // Barometric calibration
```

### LED Status Indicators

| Color          | State           | Meaning                                            |
| -------------- | --------------- | -------------------------------------------------- |
| Green (solid)  | INACTIVE        | Ready for climbing session                         |
| Red (solid)    | ACTIVE          | Session in progress, monitoring active             |
| Yellow (blink) | INCIDENT (30s)  | Fall detected, local alarm, press button to cancel |
| Yellow (solid) | INCIDENT (30s+) | Emergency sent, awaiting rescue                    |

### Setup and Deployment

1. **Configure WiFi credentials** in `ClimbingCompanion_dev.ino`:
   ```cpp
   static const char* ssid = "YOUR_WIFI_SSID";
   static const char* password = "YOUR_WIFI_PASSWORD";
   ```

2. **Set unique device serial**:
   ```cpp
   static const char* DEVICE_SERIAL = "DEV_01";  // Change for each device
   ```

3. **Upload to NodeMCU** using Arduino IDE:
   - Board: NodeMCU 1.0 (ESP-12E Module)
   - Upload Speed: 115200

4. **Register device** in web application using the `DEVICE_SERIAL` value

5. **Pair device** to user account through the dashboard

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
│   ├── dev/
│   │   └── ClimbingCompanion_dev.ino # NodeMCU code
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