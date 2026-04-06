# Climbing Companion

A safety tracker for rock climbers that connects to a wearable device. If you fall and don't move for a while, it'll send emergency alerts to your contacts via Telegram. It also tracks your climbing sessions and where you've been. Built with Flask, MongoDB, and MQTT.

## Getting Started

### What You'll Need

- Python 3.8 or newer
- MongoDB (you can run it locally or use a cloud service like Digital Ocean)
- MQTT Broker (we use HiveMQ's free public broker by default)
- A Telegram Bot Token (for sending emergency alerts)

### Installation

1. **Clone the repo**:
   ```bash
   git clone https://github.com/DoDucHoa/climbing-companion.git
   cd climbing-companion
   ```

2. **Install the required packages**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the App

```bash
python app.py
```

The server will start at `http://0.0.0.0:5000` with debug mode on.

### First Time Setup

1. **Create an account**: Go to `http://localhost:5000/register`
2. **Log in**: Use your username and password
3. **Add your device**: Register it using the serial number
4. **Set up emergency contacts**: Add people who should get alerts if something happens

## How the Device Talks to the Server

The system uses MQTT to let your wearable device talk to the server in real-time. We're using **HiveMQ's public broker** (`broker.hivemq.com:1883`) for this. All messages use **QoS 1** so they don't get lost.

### Message Topics (Channels)

Different types of messages go to different "channels" (called topics in MQTT):

| Topic Pattern                        | Who Sends It    | What It's For                                          |
| ------------------------------------ | --------------- | ------------------------------------------------------ |
| `climbing/{device_serial}/status`    | Device → Server | Tell the server if the device is paired or not         |
| `climbing/{device_serial}/telemetry` | Device → Server | Send climbing session data and sensor readings         |
| `climbing/{device_serial}/telegram`  | Device → Server | Send emergency data to your contacts                   |
| `climbing/{device_serial}/request`   | Server → Device | Tell device that someone requested data via Telegram   |

**Note**: `{device_serial}` is your device's unique ID that you register in the system.

## The Wearable Device (NodeMCU ESP8266)

The climbing companion is built using an **ESP8266 NodeMCU** board with a bunch of sensors to keep you safe while climbing.

### What's Inside

| Component       | Model/Type      | What It Does                                   |
| --------------- | --------------- | ---------------------------------------------- |
| Microcontroller | ESP8266 NodeMCU | Connects to WiFi and runs everything           |
| Environmental   | BME280          | Measures temperature, humidity, and altitude   |
| Motion Sensor   | MPU9250         | Detects falls using a 9-axis sensor            |
| GPS Module      | Generic GPS     | Tracks your location                           |
| RGB LED         | Common Anode    | Shows status with colors (red, green, yellow)  |
| Buzzer          | Active Buzzer   | Makes noise when something's wrong             |
| Push Button     | Momentary       | Start/stop sessions and cancel false alarms    |

### What It Looks Like

Here's what the actual device looks like wired up on a breadboard:

![Device Setup Photo 1](docs/images/Device%20setup%20shot%201.JPG)
*The complete device with all sensors connected*

![Device Setup Photo 2](docs/images/Device%20setup%20shot%202.JPG)
*Another view showing the wiring*

And here's the wiring diagram if you want to build your own:

![Breadboard Wiring Diagram](docs/images/Breadboard%20Wiring%20Diagram.svg)

### How the Device Works

The device switches between different modes depending on what you're doing:

#### 1. **INACTIVE** (Green LED)
- What it means: Ready and waiting
- The device sits here when it's powered on but you haven't started climbing yet
- Press the button to start a session

#### 2. **START** (Quick transition)
- What happens: Getting ready to track your climb
- Grabs your starting GPS location
- Records the starting altitude
- Notes the temperature and humidity
- Creates a session ID
- Sends a "session started" message
- Switches to ACTIVE mode

#### 3. **ACTIVE** (Red LED)
- What it means: You're climbing, and it's watching
- **Tracking height**: Records your altitude every 500ms (twice per second)
- **Watching for falls**: Constantly checks the accelerometer
  - If it detects extreme forces (<0.25g or >6.0g), it starts watching closely
  - If you don't move for 10 seconds after that, it assumes you fell
  - If you move within 5-10 seconds, it cancels the alarm (false alarm)
- Collects up to 40 altitude points before sending them to the server
- Press the button to end your session

#### 4. **INCIDENT** (Blinking Yellow LED + Buzzer beeping)
- What it means: Fall detected, no movement for 10 seconds
- **First 30 seconds**: Local alarm
  - Yellow LED blinks once per second
  - Buzzer beeps at 1kHz (on and off)
  - Press the button to cancel if it's a false alarm
- **After 30 seconds**: Sends emergency message with:
  - Your current GPS location
  - The altitude where you fell
  - Your session ID
- Keeps tracking altitude (but stops checking for more falls)

#### 5. **END** (Quick transition)
- What happens: Wrapping up your session
- Sends any altitude data that hasn't been sent yet
- Grabs your final altitude
- Sends a "session ended" message with how long you climbed
- Goes back to INACTIVE mode

### Settings You Can Change

```cpp
MONITORING_INTERVALL = 500ms      // How often it checks altitude (twice per second)
MAX_BATCH_SIZE = 40               // Altitude points per message (20 seconds worth)
INCIDENT_WAIT_TIME = 30000ms      // How long the local alarm runs before sending emergency
SEA_LEVEL_PRESSURE_HPA = 1022.0   // For calculating altitude accurately
```

### What the LED Colors Mean

| Color          | Mode            | What's Happening                                   |
| -------------- | --------------- | -------------------------------------------------- |
| Green (solid)  | INACTIVE        | Ready to start                                     |
| Red (solid)    | ACTIVE          | Tracking your climb                                |
| Yellow (blink) | INCIDENT (30s)  | Fall detected - press button to cancel             |
| Yellow (solid) | INCIDENT (30s+) | Emergency sent, help is coming                     |

### Setting Up Your Device

1. **Add your WiFi info** in `ClimbingCompanion_dev.ino`:
   ```cpp
   static const char* ssid = "YOUR_WIFI_SSID";
   static const char* password = "YOUR_WIFI_PASSWORD";
   ```

2. **Give it a unique ID**:
   ```cpp
   static const char* DEVICE_SERIAL = "DEV_01";  // Change this for each device
   ```

3. **Upload to NodeMCU** using Arduino IDE:
   - Board: NodeMCU 1.0 (ESP-12E Module)
   - Upload Speed: 115200

4. **Register the device** in the web app using that `DEVICE_SERIAL` value

5. **Pair it** to your account in the dashboard

## What's in the Project

```
├── app.py                          # Main Flask app that runs everything
├── config/
│   ├── database.yaml               # MongoDB connection settings
│   ├── mqtt_config.yaml           # MQTT broker setup
│   ├── telegram_config.yaml       # Telegram bot settings
│   ├── user_schema.yaml           # How user data is structured
│   ├── device_schema.yaml         # How device data is structured
│   ├── device_pairing_schema.yaml # How devices connect to users
│   ├── emergency_contact_schema.yaml
│   ├── climbing_session_schema.yaml
│   └── session_event_schema.yaml
├── src/
│   ├── application/
│   │   ├── api.py                 # Sets up all the API routes
│   │   ├── auth_routes.py         # Login and registration stuff
│   │   ├── base.py                # Base app class
│   │   └── routes/
│   │       ├── dt_routes.py       # Routes for device tracking
│   │       ├── dr_routes.py       # Routes for data records
│   │       ├── device_routes.py   # Device management routes
│   │       ├── dt_management_routes.py
│   │       └── emergency_contact_routes.py
│   ├── digital_twin/
│   │   ├── core.py                # Main device tracking logic
│   │   └── dt_factory.py          # Creates and manages device trackers
│   ├── dev/
│   │   └── ClimbingCompanion_dev.ino # Arduino code for the NodeMCU
│   ├── services/
│   │   ├── base.py                # Base service class
│   │   ├── database_service.py    # Talks to MongoDB
│   │   ├── mqtt_service.py        # Handles device messages
│   │   ├── telegram_service.py    # Sends alerts via Telegram
│   │   └── analytics.py           # Crunches climbing data
│   └── virtualization/
│       ├── digital_replica/
│       │   ├── dr_factory.py      # Creates data records with Pydantic
│       │   └── schema_registry.py # Manages data schemas
│       └── registry.py
├── templates/                      # HTML pages
│   ├── login.html
│   ├── register.html
│   └── home.html
├── static/                         # CSS and images
├── tests/                          # Tests
└── docs/                           # More documentation
```

## Security Warning

⚠️ **Heads up - this is for demo/learning purposes:**
- Passwords are stored as plain text (really bad, don't do this in production)
- No encryption on sessions or JWT tokens
- Just basic authentication, nothing fancy
- No rate limiting (someone could spam the API)

If you're going to use this for real, you'll need to fix these security issues first.

## More Info

- [Testing Guide](docs/Testing%20Guide.md) - How to test everything
- [MQTT Message Exchange Formats](docs/MQTT%20Message%20Exchange%20Formats.md) - Details on all the MQTT messages and topics


**Built with:** Flask 3.1.0 | MongoDB | Pydantic | MQTT | Telegram Bot API