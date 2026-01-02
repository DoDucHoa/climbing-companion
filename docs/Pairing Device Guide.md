# Pairing Device Guide

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

### Step 1: Register User and Device

1. **Register/Login** to the web interface:
   - Navigate to `http://localhost:5000`
   - Register a new account or login
   
2. **Register a device**:
   - Click on "Devices" tab
   - Enter serial number
   - Click "Register Device"
   - Device will appear with status "Inactive" (gray badge)

### Step 2: Simulate Device Connection using HiveMQ WebSocket Client

1. **Open HiveMQ WebSocket Client**:
   - Go to: https://www.hivemq.com/demos/websocket-client/
   
2. **Connect to Broker**:
   - Click "Connect" (uses default settings)

### Step 3: Send Status Message (Activate Device)

1. **Publish Status Message**:
   - **Topic**: `climbing/[Your input serial number]/status`
   - **QoS**: 1
   - **Payload**:
     ```json
     {
       "status": "active"
     }
     ```
   - Click "Publish"

2. **Check Server Logs**:
   You should see:
   ```
   INFO - Received message on topic: climbing/[Your input serial number]/status
   INFO - Processing status update for device: [Your input serial number]
   INFO - Device [Your input serial number] connected for first time, activating...
   INFO - Device status updated: [Your input serial number] -> active
   ````

3. **Refresh Web UI**:
   - Refresh the page
   - Device status should now show "Active" (green badge)
   - Last Sync timestamp should be updated

## Expected Behavior

### Successful Flow
1. ✅ User registers device on web → Device created with status="inactive" in database
2. ✅ Device sends status → Device updates to status="active" in database

### Data Flow
```
Device (HiveMQ Client) -> MQTT Message (QoS 1) -> HiveMQ Broker (broker.hivemq.com) -> Flask Application (MQTTService) -> Schema Validation -> MongoDB Storage -> Web UI Display
```