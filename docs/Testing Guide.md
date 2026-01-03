# Pairing Device Flow Guide

## Prerequisites

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the Flask application**:
   ```bash
   python app.py
   ```

   The application should start on `http://localhost:5000` and you should see:
   ```
   INFO - MQTT Service initialized successfully
   INFO - Connected to MQTT broker successfully
   INFO - Subscribed to topic: climbing/+/status
   ```

## Testing Flow

### Simulate Device Connection using HiveMQ WebSocket Client

1. **Open HiveMQ WebSocket Client**:
   - Go to: https://www.hivemq.com/demos/websocket-client/
   
2. **Connect to Broker**:
   - Click "Connect" (uses default settings)

### Send Status Message (Activate Device)

**Publish Status Message**:
   - **Topic**: `climbing/[Device Serial]/status`
   - **QoS**: 1
   - **Payload**:
     ```json
     {
       "status": "active"
     }
     ```
   - Click "Publish"

## Expected Behavior

### Successful Flow
1. ✅ User registers device on web → Device created with status="inactive" in database
2. ✅ Device sends status → Device updates to status="active" in database


---

# Climbing Session Flow Guide

## Preparation

### Required Information
1. **Device Serial Number**: Get from Home page → Devices tab
2. **Session ID**: Generate your own UUID

### MQTT Connection
1. Open https://www.hivemq.com/demos/websocket-client/
2. Click **Connect**
3. Wait for status to show "Connected"

---

## Test Flow

### Step 1: START Session

**Topic:** `climbing/[Device Serial]/telemetry`  
**Payload:**
```json
{
  "session_state": "START",
  "session_id": "test_session_001",
  "alt": 1500.0,
  "temp": 25.5,
  "humidity": 60,
  "latitude": 21.0285,
  "longitude": 105.8542
}
```
---

### Step 2: ACTIVE Session - Batch 1 (Initial Climb)

**Topic:** `climbing/[Device Serial]/telemetry`  
**Payload:** (Device buffered 30 seconds of data - steady climb)
```json
{
  "session_state": "ACTIVE",
  "session_id": "test_session_001",
  "trace": [
    {"height": 1.2, "time": 5},
    {"height": 3.8, "time": 10},
    {"height": 7.5, "time": 15},
    {"height": 11.2, "time": 20},
    {"height": 14.0, "time": 25},
    {"height": 18.5, "time": 30}
  ]
}
```
---

### Step 3: ACTIVE Session - Batch 2 (Challenging Section with Pauses)

**Topic:** `climbing/ESP32_ABC123/telemetry`  
**Payload:** (Next 30 seconds - slower progress, some descents)
```json
{
  "session_state": "ACTIVE",
  "session_id": "test_session_001",
  "trace": [
    {"height": 20.5, "time": 35},
    {"height": 22.8, "time": 40},
    {"height": 21.5, "time": 45},
    {"height": 24.0, "time": 50},
    {"height": 27.5, "time": 55},
    {"height": 26.0, "time": 60}
  ]
}
```
---

### Step 4: ACTIVE Session - Batch 3 (Final Push with Variations)

**Topic:** `climbing/[Device Serial]/telemetry`  
**Payload:** (20 data points with realistic climbing patterns)
```json
{
  "session_state": "ACTIVE",
  "session_id": "test_session_001",
  "trace": [
    {"height": 28.5, "time": 65},
    {"height": 32.0, "time": 70},
    {"height": 35.5, "time": 75},
    {"height": 38.0, "time": 80},
    {"height": 36.5, "time": 85},
    {"height": 39.0, "time": 90},
    {"height": 42.5, "time": 95},
    {"height": 45.0, "time": 100},
    {"height": 43.5, "time": 105},
    {"height": 47.0, "time": 110},
    {"height": 50.5, "time": 115},
    {"height": 53.0, "time": 120},
    {"height": 51.5, "time": 125},
    {"height": 54.5, "time": 130},
    {"height": 57.0, "time": 135},
    {"height": 60.5, "time": 140},
    {"height": 62.0, "time": 145},
    {"height": 64.5, "time": 150},
    {"height": 66.0, "time": 155},
    {"height": 68.5, "time": 160}
  ]
}
```

**Note:** Height variations simulate real climbing behavior - some descents for repositioning, variable progress rates

---
### Step 5: END Session

**Topic:** `climbing/[Device Serial]/telemetry`  
**Payload:**
```json
{
  "session_state": "END",
  "session_id": "test_session_001",
  "alt": 1570.0,
  "time": 180
}
```

---

## Test Case: INCIDENT

```json
{
  "session_state": "INCIDENT",
  "session_id": "test_session_002",
  "alt": 1545.0,
  "time": 90,
  "latitude": 21.0290,
  "longitude": 105.8550
}
```

**Expected Result:**
- **Telegram alert** sent to emergency contacts

---

# Send Telemetry Data to Telegram
## Step 1: Get Telegram chat ID
On Telegram, search for `@userinfobot` and send `/start` message, the bot will response back to you with the `Id`


## Step 2: Send telemetry data to emergency contact
On HiveMQ Broker

**Publish Status Message**:
   - **Topic**: `climbing/[Device Serial]/telegram`
   - **QoS**: 1
   - **Payload**:
     ```json
     {
        "chat_id": "telegram_chat_id", // remember to change this <==========
        "user_name": "Test Climber", // user_name get from server publish message when emergency contact request
        "session_state": "ACTIVE", // START or ACTIVE
        "session_id": "uuid4", // id generate from uuid
        "latitude": 21.028511,
        "longitude": 105.804817,
        "alt": 1250.5,
        "temp": 18.5,
        "humidity": 65.0
      }
     ```
   - Click "Publish"
   - **Expected result**: your Telegram account will receive an alert message from ClimbingCompanion bot

## Subscribe `/check_status` event from the server
On HiveMQ Broker, subscribe to this topic `climbing/[Device Serial]/request`

You will receive a message with this format:

```json
{
  "request_type": "status_check",
  "chat_id": "telegram_chat_id",
  "user_id": "71d6c21e-e4b7-4c8b-b49f-758ea770bf04",
  "user_name": "DUC HOA DO",
  "contact_name": "DUC HOA DO",
  "timestamp": "2026-01-03T19:10:24.601859"
}
```