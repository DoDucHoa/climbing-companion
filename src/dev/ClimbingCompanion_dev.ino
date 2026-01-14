#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include "MPU9250.h"
#include <TinyGPSPlus.h>
#include <SoftwareSerial.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// --- Configuration ---
static const char* ssid = ""; // Name of the WiFi to connent to
static const char* password = "";  // Password of the WiFi to connect to
static const char* mqtt_server = "broker.mqttdashboard.com";
static const char* mqtt_namespace = "climbing/";
static const char* DEVICE_SERIAL = "DEV_01"; // This needs to be changed for every device

static const uint32_t SERIAL_BAUD = 115200;
static const uint32_t GPS_BAUD = 9600;
static const float SEA_LEVEL_PRESSURE_HPA = 1022.0; // Sea Level Pressure in hPa, may vary.

static const uint32_t MONITORING_INTERVALL = 500;  // Altitude is tracked in 2Hz frequency (every 500 ms)
static const uint16_t MAX_BATCH_SIZE = 40; // Number of altitude points that are buffered
static const uint32_t INCIDENT_WAIT_TIME = 30000; // Local Alarm Time

// --- Pin Mapping ---
static const uint8_t PIN_RGB_B = D0;
static const uint8_t PIN_RGB_G = D1;
static const uint8_t PIN_RGB_R = D2;
static const uint8_t PIN_BUTTON = D3;
static const uint8_t PIN_BUZZER = D4;
static const uint8_t PIN_SCL = D5;
static const uint8_t PIN_SDA = D6;
static const uint8_t PIN_GPS_RX = D7;
static const uint8_t PIN_GPS_TX = D8;

// --- Data Structures ---
struct TracePoint {
    uint32_t time;   // miliseconds since start
    float height;    // Altitude delta in meters    
};

struct SessionData {
    String state; // INACTIVE, START, ACTIVE, INCIDENT, END
    String id;
    float temp;
    float humidity;
    float alt;  // GPS altitude
    float latitude;
    float longitude;
    uint32_t startTime;
    uint32_t endTime;
    uint32_t lastAltLog;
    uint32_t incidentTime;
    float start_alt_bar;    // barometric start altitude
    TracePoint trace[MAX_BATCH_SIZE];
} currentSession;

//  --- Topic Strings ---
String TOPIC_STATUS    = String(mqtt_namespace) + String(DEVICE_SERIAL) + "/status";
String TOPIC_TELEMETRY = String(mqtt_namespace) + String(DEVICE_SERIAL) + "/telemetry";
String TOPIC_REQUEST   = String(mqtt_namespace) + String(DEVICE_SERIAL) + "/request";
String TOPIC_TELEGRAM = String(mqtt_namespace) + String(DEVICE_SERIAL) + "/telegram";
String TOPIC_INCIDENT = String(mqtt_namespace) + String(DEVICE_SERIAL) + "/incident";

// --- Objects & Global states ---
Adafruit_BME280 bme;
MPU9250 mpu;
SoftwareSerial gpsSerial(PIN_GPS_RX, PIN_GPS_TX);
TinyGPSPlus gps;
WiFiClient espClient;
PubSubClient mqttClient(espClient);
uint16_t currentLogIndex = 0; 

// --- Device Setup ---
void setup() {
    // Define internal communciation parameters
    Serial.begin(SERIAL_BAUD);
    gpsSerial.begin(GPS_BAUD);
    Wire.begin(PIN_SDA, PIN_SCL);
    Wire.setClock(400000);

    // Initialization of the Arduino Pins
    pinMode(PIN_RGB_R, OUTPUT);
    pinMode(PIN_RGB_G, OUTPUT);
    pinMode(PIN_RGB_B, OUTPUT);
    pinMode(PIN_BUTTON, INPUT_PULLUP);
    pinMode(PIN_BUZZER, OUTPUT);
    
    // Wake up sound
    tone(PIN_BUZZER, 2000);
    delay(200);
    tone(PIN_BUZZER, 2500);
    delay(200);
    tone(PIN_BUZZER, 3000);
    delay(200);
    tone(PIN_BUZZER, 4000);
    delay(200);
    noTone(PIN_BUZZER);
    
    // BME280 Setup
    if (!bme.begin(0x76, &Wire)) { Serial.println(F("BME Error")); while(1); }
    bme.setSampling(Adafruit_BME280::MODE_NORMAL,
                    Adafruit_BME280::SAMPLING_X2,  
                    Adafruit_BME280::SAMPLING_X16, 
                    Adafruit_BME280::SAMPLING_X1,  
                    Adafruit_BME280::FILTER_X16,
                    Adafruit_BME280::STANDBY_MS_500);

    // MPU9250 Setup
    MPU9250Setting setting;
    setting.accel_fs_sel = ACCEL_FS_SEL::A8G;
    setting.accel_dlpf_cfg = ACCEL_DLPF_CFG::DLPF_45HZ;

    if (!mpu.setup(0x68, setting)) { Serial.println(F("MPU Error")); while(1); }

    // WiFi and MQTT Setup
    WiFi.begin(ssid, password);
    reconnectWiFi();
    mqttClient.setServer(mqtt_server, 1883);
    mqttClient.setBufferSize(2048);
    mqttClient.setCallback(mqttCallback);
    reconnectMQTT();
    setLEDColor(0, 0, 0);

    // Setup finished, notify the server we are online
    sendDeviceActive();
    currentSession.state = "INACTIVE";
    Serial.println(F("System Online. Press Button to begin climb."));

    // Ready sound
    tone(PIN_BUZZER, 3000);
    delay(200);
    tone(PIN_BUZZER, 4000);
    delay(200);
    noTone(PIN_BUZZER);
}

// --- Main Loop Logic ---

void loop() {
    if (WiFi.status() != WL_CONNECTED) reconnectWiFi();
    if (!mqttClient.connected()) reconnectMQTT();
    mqttClient.loop();

    handleButton();

    while (gpsSerial.available() > 0) {
        gps.encode(gpsSerial.read());
    }

    stateMachine();
}

// --- Function so set the RGB LED to indicate the device status ---
void setLEDColor(int r, int g, int b) {
    analogWrite(PIN_RGB_R, r);
    analogWrite(PIN_RGB_G, g);
    analogWrite(PIN_RGB_B, b); 
}


// --- Connectivity Functions ---

void reconnectWiFi() {
    Serial.print("Connecting WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        // Blink LED GREEN
        if ((millis() / 500) % 2 == 0) {
            setLEDColor(0, 0, 255); 
        } else {
            setLEDColor(0, 0, 0);
        }
    }
    Serial.println("\nWiFi Connected");
    setLEDColor(0, 0, 0);
}

void reconnectMQTT() {
    Serial.print("Connecting MQTT");
    while (!mqttClient.connected()) {
        String clientId = String(DEVICE_SERIAL);    // all the devices must have different names
        if (mqttClient.connect(clientId.c_str())) {
            mqttClient.subscribe(TOPIC_REQUEST.c_str());
            Serial.println("\nMQTT Connected");
        } else {
            delay(500); 
            Serial.print(".");
            // Blink LED GREEN
            if ((millis() / 500) % 2 == 0) {
                setLEDColor(0, 0, 255); 
            } else {
                setLEDColor(0, 0, 0);
            }
        }
    }
}

// --- Flow Functions ---

void stateMachine() {
    if (currentSession.state == "INACTIVE") {
        setLEDColor(0, 255, 0); // Steady Green
    } 

    else if (currentSession.state == "START") {
        startClimb();
    } 
    
    else if (currentSession.state == "ACTIVE") {
        setLEDColor(255, 0, 0); // Solid Red
        runSessionLogic();      // Monitor altitude and motion data
    } 

    else if (currentSession.state == "END") {
        stopClimb();
    } 
    
    else if (currentSession.state == "INCIDENT") {
        runIncidentLogic();     // Handle the incident alarm
        runSessionLogic();      // Monitor altitude, fall detection is left out internally 
    }
}

void handleButton() {
    static bool lastBtnState = LOW; 
    bool currentBtnState = digitalRead(PIN_BUTTON);

    if (currentBtnState == LOW && lastBtnState == HIGH) {         
        // --- Transition Logic ---
        if (currentSession.state == "INACTIVE") {
            currentSession.state = "START";
        } 
        else if (currentSession.state == "ACTIVE") {
            currentSession.state = "END";
        }
        else if (currentSession.state == "INCIDENT") {
            // Cancel Alarm: Reset back to ACTIVE
            currentSession.state = "ACTIVE";
            noTone(PIN_BUZZER); 
            Serial.println("Incident Cancelled by User");
        }
        // Sound feedback
        tone(PIN_BUZZER, 2500);
        delay(80);
        noTone(PIN_BUZZER);
    }
    lastBtnState = currentBtnState;
}

// --- Functions for the climbing functionalties ---

void startClimb() {
    currentSession.state = "START";
    // Create a new ID
    currentSession.id = String(ESP.getChipId(), HEX) + "_" + String(millis()) + "_" + String(random(0xFFFF), HEX);

    // Snapshot at start
    currentSession.temp = bme.readTemperature();
    currentSession.humidity = bme.readHumidity();
    currentSession.alt = gps.altitude.isValid() ? gps.altitude.meters() : bme.readAltitude(SEA_LEVEL_PRESSURE_HPA);
    currentSession.latitude = gps.location.isValid() ? gps.location.lat() : 0.0;
    currentSession.longitude = gps.location.isValid() ? gps.location.lng() : 0.0;
    currentSession.start_alt_bar = bme.readAltitude(SEA_LEVEL_PRESSURE_HPA);

    // Reset the other session data
    // memset(currentSession.trace, 0, sizeof(currentSession.trace)); // Decide if the reset is really necessary
    currentSession.startTime = millis();
    currentSession.endTime = 0;
    currentSession.lastAltLog = 0;
    currentSession.incidentTime = 0;
    currentLogIndex = 0;
    
    // Send the Start Message
    sendStartSession();

    Serial.println("Climbing Session started.");

    // After start of the session was published, update the LED and state
    setLEDColor(255, 0, 0); // Red: Session Active
    currentSession.state = "ACTIVE";
}

void stopClimb() {
    // First, send all pending Session data
    sendActiveSession();

    // Now end the session
    currentSession.state = "END";
    currentSession.alt = gps.altitude.isValid() ? gps.altitude.meters() : bme.readAltitude(SEA_LEVEL_PRESSURE_HPA);
    currentSession.endTime = millis();

    // Send the End Message
    sendEndSession();

    Serial.println("Climbing Session ended.");

    // After end of the session was published, update the LED and state
    setLEDColor(0, 255, 0); // Green: Session inactive
    currentSession.state = "INACTIVE";
    currentSession.id = "-";
}

void runSessionLogic() {
    // 1. Altitude Tracking
    if (millis() - currentSession.lastAltLog >= MONITORING_INTERVALL) {        
        currentSession.lastAltLog = millis();
        currentSession.trace[currentLogIndex].time = millis() - currentSession.startTime;
        currentSession.trace[currentLogIndex].height = bme.readAltitude(SEA_LEVEL_PRESSURE_HPA) - currentSession.start_alt_bar;
        currentLogIndex++;

        if (currentLogIndex >= MAX_BATCH_SIZE) {
            sendActiveSession();
        }
    }

    // 2. Fall Detection
    if (currentSession.state == "INCIDENT") return; // If an incident was already detected, skip
    if (mpu.update()) {
        static uint32_t triggerTime = 0; // 0 means we are currently "IDLE"
        float g = sqrt(pow(mpu.getAccX(), 2) + pow(mpu.getAccY(), 2) + pow(mpu.getAccZ(), 2));
        uint32_t now = millis();

        // Initial Trigger: If we aren't already tracking a fall
        if (triggerTime == 0) {
            if (g < 0.25 || g > 6.0) {
                triggerTime = now;
                Serial.println("Fall detected! Monitoring for stillness...");
            }
        } 
       // Monitoring for stillness
        else {
            uint32_t elapsed = now - triggerTime;
            // If movement is detected during the "Stillness Check" (between 5s and 10s)
            if (elapsed > 5000 && (g < 0.85 || g > 1.15)) {
                triggerTime = 0; // RESET: They moved, so they are likely okay
                Serial.println("Movement detected: Incident Canceled.");
                return;
            }

            // If 10 seconds have passed without a reset
            if (elapsed >= 10000) {
                currentSession.state = "INCIDENT";
                currentSession.incidentTime = now;
                triggerTime = 0; // Reset for next time
                Serial.println("!!! INCIDENT: Motionless after fall !!!");
            }
        }
    }
}

// --- Incident function ---
void runIncidentLogic() {
    uint32_t now = millis();
    uint32_t elapsed = now - currentSession.incidentTime;

    if (elapsed < INCIDENT_WAIT_TIME) {
        // Local Warning: Blink Yellow + Buzz
        if ((now / 500) % 2 == 0) {
            setLEDColor(255, 255, 0); 
            tone(PIN_BUZZER, 1000);
        } else {
            setLEDColor(0, 0, 0);
            noTone(PIN_BUZZER);
        }
    } else {
        // Timer Expired: Emergency
        setLEDColor(255, 255, 0); // Solid Yellow
        
        // We only want to send the MQTT message ONCE
        static String lastSentIncidentId = "";
        if (lastSentIncidentId != currentSession.id) {
            // Fetch necessary incident data
            currentSession.alt = gps.altitude.isValid() ? gps.altitude.meters() : bme.readAltitude(SEA_LEVEL_PRESSURE_HPA);
            currentSession.latitude = gps.location.isValid() ? gps.location.lat() : 39.23;      // Default values for demo
            currentSession.longitude = gps.location.isValid() ? gps.location.lng() : 9.10769;   // Default values for demo

             // Send the Incident Message
            sendIncident();
            lastSentIncidentId = currentSession.id;
            Serial.println("MQTT Incident Sent!");
        }

        // Beep shortly every 10 seconds
        static uint32_t beepTime = now; 
        if (now - beepTime > 10000) {
            beepTime = now;
            setLEDColor(0, 0, 0); // Solid Yellow
            tone(PIN_BUZZER, 1000);
            delay(200);
            setLEDColor(255, 255, 0); // Solid Yellow
            noTone(PIN_BUZZER);
        }
    }
}

// --- Functions to send, receive and create MQTT messages---

void publishMqttMessage(DynamicJsonDocument doc, String topic) {
    String out;
    serializeJson(doc, out);
    // Serial.print(topic);  Serial.print(": "); Serial.println(out); // for debug
    mqttClient.publish(topic.c_str(), out.c_str());
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    Serial.print("Message arrived on topic : ");
    Serial.print(topic);
    Serial.println("");

    // 1. Parse the incoming JSON request
    StaticJsonDocument<512> filter; // Use a filter to save RAM if the message is huge
    filter["request_type"] = true;
    filter["chat_id"] = true;
    filter["user_name"] = true;

    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload, length);

    if (error) {
        Serial.print(F("deserializeJson() failed: "));
        Serial.println(error.f_str());
        return;
    }
    
    // 2. Handle "status_check"
    if (doc["request_type"] == "status_check") {
        const char* chat_id = doc["chat_id"];
        const char* user_name = doc["user_name"];
        
        Serial.print("Status requested by: ");
        Serial.println(user_name);

        // Update data for status
        currentSession.temp = bme.readTemperature();
        currentSession.humidity = bme.readHumidity();
        currentSession.alt = gps.altitude.isValid() ? gps.altitude.meters() : bme.readAltitude(SEA_LEVEL_PRESSURE_HPA);
        currentSession.latitude = gps.location.isValid() ? gps.location.lat() : 0.0;
        currentSession.longitude = gps.location.isValid() ? gps.location.lng() : 0.0;

        // 3. Send the Response
        sendRemoteStatusResponse(chat_id, user_name);
    }
}

void sendDeviceActive() {
    DynamicJsonDocument doc(128);
    doc["status"] = "active";

    publishMqttMessage(doc, TOPIC_STATUS);
}

void sendStartSession() {
    if (currentSession.state != "START") {
        Serial.print("WARNING: Start session message is sent from state: ");
        Serial.println(currentSession.state);
    }

    DynamicJsonDocument doc(512);
    doc["session_state"] = currentSession.state;
    doc["session_id"] = currentSession.id;
    doc["alt"] = currentSession.alt;
    doc["temp"] = currentSession.temp;
    doc["humidity"] = currentSession.humidity;
    doc["latitude"] = currentSession.latitude;
    doc["longitude"] = currentSession.longitude;
    
    publishMqttMessage(doc, TOPIC_TELEMETRY);

    Serial.println("Start message published.");
}

void sendActiveSession() {
    if (currentSession.state != "ACTIVE" && currentSession.state != "INCIDENT") {
        Serial.print("WARNING: Active Session message is sent from state: ");
        Serial.println(currentSession.state);
    }

    if (currentLogIndex == 0) return;

    const size_t capacity = JSON_ARRAY_SIZE(currentLogIndex) + currentLogIndex * JSON_OBJECT_SIZE(2) + 200;
    DynamicJsonDocument doc(capacity);
    // If we are in an incident currently, the session data state has to be active to be saved
    doc["session_state"] = currentSession.state=="INCIDENT"?"ACTIVE":currentSession.state; 
    doc["session_id"] = currentSession.id;
    
    JsonArray traceArr = doc.createNestedArray("trace");
    for (int i = 0; i < currentLogIndex; i++) {
        JsonObject p = traceArr.createNestedObject();
        p["height"] = currentSession.trace[i].height;
        p["time"] = currentSession.trace[i].time / 1000.0;
    }

    publishMqttMessage(doc, TOPIC_TELEMETRY);
    currentLogIndex = 0; // Reset batch index after successful send

    Serial.println("Active message published.");
}

void sendIncident() {
    if (currentSession.state != "INCIDENT") {
        Serial.print("WARNING: Incident message is sent from state: ");
        Serial.println(currentSession.state);
    }

    DynamicJsonDocument doc(512);
    doc["session_state"] = currentSession.state;
    doc["session_id"] = currentSession.id;
    doc["alt"] = currentSession.alt;
    doc["time"] = (currentSession.incidentTime - currentSession.startTime) / 1000.0;
    doc["latitude"] = currentSession.latitude;
    doc["longitude"] = currentSession.longitude;
    
    publishMqttMessage(doc, TOPIC_INCIDENT);

    Serial.println("Incident message published.");
}

void sendEndSession() {
    if (currentSession.state != "END") {
        Serial.print("WARNING: End session message is sent from state: ");
        Serial.println(currentSession.state);
    }

    DynamicJsonDocument doc(256);
    doc["session_state"] = currentSession.state;
    doc["session_id"] = currentSession.id;
    doc["alt"] = currentSession.alt;
    doc["time"] = (currentSession.endTime - currentSession.startTime) / 1000.0;

    publishMqttMessage(doc, TOPIC_TELEMETRY);

    Serial.println("End message published.");
}

void sendRemoteStatusResponse(const char* chat_id, const char* user_name) {
    DynamicJsonDocument doc(1024);

    doc["chat_id"] = chat_id;         // Echo back the chat_id from the request
    doc["user_name"] = user_name;     // Use the user_name from the request
    doc["session_state"] = currentSession.state;
    doc["session_id"] = currentSession.id;
    doc["latitude"] = currentSession.latitude;
    doc["longitude"] = currentSession.longitude;
    doc["alt"] = currentSession.alt;
    doc["temp"] = currentSession.temp;
    doc["humidity"] = currentSession.humidity;

    publishMqttMessage(doc, TOPIC_TELEGRAM);

    Serial.println("Status message published.");
}