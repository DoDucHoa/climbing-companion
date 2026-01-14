# MQTT Message Exchange Formats

## Topic Structure
### Topic Naming Convention
All topics follow the pattern: `climbing/{device_serial}/{message_type}`

### Subscribed Topics (Server)
| Topic Pattern          | Description            | Wildcard     |
| ---------------------- | ---------------------- | ------------ |
| `climbing/+/status`    | Device status updates  | Single-level |
| `climbing/+/telemetry` | Session telemetry data | Single-level |
| `climbing/+/incident`  | Emergency incidents    | Single-level |
| `climbing/+/telegram`  | Telegram bot responses | Single-level |

### Published Topics (Server → Device)
| Topic Pattern               | Description              |
| --------------------------- | ------------------------ |
| `climbing/{serial}/request` | Status request to device |

### Topic Examples
```
climbing/DEVICE-001/status
climbing/DEVICE-001/telemetry
climbing/DEVICE-001/incident
climbing/DEVICE-001/telegram
climbing/DEVICE-001/request
```

---

## Message Types

### Overview of Message Types

| Type              | Direction       | Topic Suffix | Purpose                           |
| ----------------- | --------------- | ------------ | --------------------------------- |
| Status            | Device → Server | `/status`    | Device connectivity and health    |
| Telemetry         | Device → Server | `/telemetry` | Session data and measurements     |
| Incident          | Device → Server | `/incident`  | Emergency fall/accident detection |
| Telegram Response | Device → Server | `/telegram`  | Response to status queries        |
| Device Request    | Server → Device | `/request`   | Request device status             |

---

## Device-to-Server Messages

### 1. Status Message

**Topic:** `climbing/{serial_number}/status`  
**Purpose:** Notify server of device online/offline state  
**Frequency:** On connection, periodic heartbeat, or state change

#### Payload Structure
```json
{
  "status": "active"
}
```

#### Status Values
- `active` - Device is online and operational
- `inactive` - Device is offline or disconnected

#### Behavior
- First connection transitions device from `inactive` to `active`
- Triggers auto-pairing if device is newly registered

---

### 2. Telemetry Message (Session Data)

**Topic:** `climbing/{serial_number}/telemetry`  
**Purpose:** Stream climbing session data and sensor measurements  
**Frequency:** On session state changes and periodic during active climbing

#### 2.1 Session START State

##### Payload Structure
```json
{
  "session_state": "START",
  "session_id": "string",
  "alt": float,
  "temp": float,
  "humidity": float,
  "latitude": float,
  "longitude": float
}
```

##### Example Payload
```json
{
  "session_state": "START",
  "session_id": "session_id_001",
  "alt": 1250.5,
  "temp": 18.3,
  "humidity": 65.2,
  "latitude": 46.8182,
  "longitude": 8.2275
}
```

##### Behavior
- Creates new `climbing_session` record in database
- Creates initial `session_event` with baseline height (0m) and time (0s)
- Records environmental conditions at session start
- Links session to user via device pairing

---

#### 2.2 Session ACTIVE State

##### Payload Structure
```json
{
  "session_state": "ACTIVE",
  "session_id": "string",
  "trace": [
    {
      "height": float,
      "time": int
    }
  ]
}
```

##### Example Payload
```json
{
  "session_state": "ACTIVE",
  "session_id": "session_id_001",
  "trace": [
    {
      "height": 2.5,
      "time": 15
    },
    {
      "height": 4.8,
      "time": 30
    },
    {
      "height": 7.2,
      "time": 45
    },
    {
      "height": 9.1,
      "time": 60
    }
  ]
}
```

##### Trace Array Format
- `height` - Climbing height in meters relative to start altitude
- `time` - Elapsed time in seconds since session start

##### Behavior
- Updates `climbing_session` state to ACTIVE (if not already)
- Creates new `session_event` record with trace data
- Supports buffered data transmission (multiple trace points per message)
- Trace points represent sensor readings accumulated since last transmission

---

#### 2.3 Session END State

##### Payload Structure
```json
{
  "session_state": "END",
  "session_id": "string",
  "alt": float
}
```

##### Example Payload
```json
{
  "session_state": "END",
  "session_id": "session_id_001",
  "alt": 1262.3
}
```

##### Behavior
- Updates `climbing_session` with END state
- Records final altitude (sea level) and end timestamp

---

### 3. Incident Message (Emergency Alert)

**Topic:** `climbing/{serial_number}/incident`  
**Purpose:** Report fall detection or emergency situation  
**Frequency:** Immediately upon incident detection  

#### Payload Structure
```json
{
  "session_id": "string",
  "alt": float,
  "time": int,
  "latitude": float,
  "longitude": float
}
```

#### Example Payload
```json
{
  "session_id": "session_id_001",
  "alt": 1258.7,
  "time": 125,
  "latitude": 46.8185,
  "longitude": 8.2278
}
```

#### Behavior
- Updates `climbing_session` state to INCIDENT
- Creates `session_event` with incident trace point
- Calculates incident height relative to session start
- **Triggers emergency Telegram alerts** to user's registered emergency contacts
- Includes location data for rescue coordination

---

### 4. Telegram Response Message

**Topic:** `climbing/{serial_number}/telegram`  
**Purpose:** Provide device status in response to Telegram bot status request  
**Frequency:** On-demand, triggered by user query via Telegram bot

#### Payload Structure
```json
{
  "chat_id": int,
  "user_name": "string",
  "user_id": "string",
  "session_state": "string",
  "latitude": float,
  "longitude": float,
  "alt": float,
  "temp": float,
  "humidity": float,
  "session_id": "string"
}
```

#### Example Payload
```json
{
  "chat_id": 123456789,
  "user_name": "Climber Name",
  "user_id": "user_123",
  "session_state": "ACTIVE",
  "latitude": 46.8185,
  "longitude": 8.2278,
  "alt": 1258.7,
  "temp": 17.8,
  "humidity": 62.5,
  "session_id": "session_id_001"
}
```

#### Session State Values
- `START` - Session just initiated
- `ACTIVE` - Currently climbing
- `END` - Session completed
- `INCIDENT` - Emergency detected
- `UNKNOWN` - No active session or state undetermined

#### Behavior
- Server forwards response to Telegram bot service
- Bot sends formatted status message to requesting user
- Includes location map link if coordinates available
- Response timeout: 30 seconds

---

## Server-to-Device Messages

### Device Status Request

**Topic:** `climbing/{serial_number}/request`  
**Purpose:** Request current status from device (typically for Telegram bot queries)  
**Direction:** Server → Device

#### Payload Structure
```json
{
  "timestamp": "ISO8601",
  "chat_id": int,
  "user_id": "string",
  "user_name": "string"
}
```

#### Example Payload
```json
{
  "timestamp": "2026-01-14T14:35:22.123Z",
  "chat_id": 123456789,
  "user_id": "user_123",
  "user_name": "Climber Name"
}
```

#### Expected Response
Device should respond with a **Telegram Response Message** on topic `climbing/{serial_number}/telegram` containing current status information.

---

## Quality of Service (QoS)

### QoS Levels Used

| Operation              | QoS Level | Rationale                                         |
| ---------------------- | --------- | ------------------------------------------------- |
| Subscribe (all topics) | QoS 1     | At least once delivery ensures no missed messages |
| Publish (all messages) | QoS 1     | Guarantees message delivery for critical data     |
---

## Message Encoding

- **Format:** JSON (JavaScript Object Notation)
- **Character Encoding:** UTF-8
- **Payload Size:** Recommended maximum 1024 bytes per message
- **Number Format:** 
  - Floats: Up to 2 decimal places for precision
  - Integers: Standard JSON integer format
- **Timestamp Format:** ISO 8601 (UTC)