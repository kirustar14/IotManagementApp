#include "ECE140_WIFI.h"
#include "ECE140_MQTT.h"
#include <ArduinoJson.h>
#include <WiFi.h>  
#include <Adafruit_BMP085.h>

// Wifi + MQTT client credentials 
const char* ucsdUsername = UCSD_USERNAME;
const char* ucsdPassword = UCSD_PASSWORD;
const char* wifiSsid = WIFI_SSID;
const char* clientID = CLIENT_ID; 
const char* topicPrefix = TOPIC_PREFIX; 

ECE140_MQTT mqtt(CLIENT_ID, TOPIC_PREFIX);

ECE140_WIFI wifi;

Adafruit_BMP085 bmp; //BMP Sensor Instance 


// Function to get the unique device ID (MAC address)
String getDeviceID() {
    uint8_t mac[6];
    WiFi.macAddress(mac);  // Get the MAC address of the ESP32
    String deviceID = "";
    for (int i = 0; i < 6; i++) {
        deviceID += String(mac[i], HEX);  // Convert each byte to hex and concatenate
    }
    deviceID.toUpperCase();  // Optional: convert to uppercase for consistency
    return deviceID;
}

// Function to format data as a string and publish it
void publishSensorData() {
    // Read the temperature and pressure from BMP sensor
    float temperatureBMP = bmp.readTemperature(); // Read temperature from BMP sensor
    int pressure = bmp.readPressure(); // Read pressure from BMP sensor
    String deviceID = getDeviceID();  // Get the unique device ID

    // Debugging: Print values to Serial Monitor
    Serial.println("=== Sensor Readings ===");
    Serial.print("Device ID: "); Serial.println(deviceID);
    Serial.print("Temp: "); Serial.print(temperatureBMP); Serial.println(" C");
    Serial.print("Pressure: "); Serial.print(pressure); Serial.println(" Pa");
    Serial.println("=======================\n");

    // Construct the JSON payload
    StaticJsonDocument<1024> doc;
    doc["device_id"] = deviceID;
    doc["temperature"] = temperatureBMP;
    doc["pressure"] = pressure;

    // Serialize JSON to a string
    String jsonString;
    serializeJson(doc, jsonString);

    // Publish the message to MQTT topic
    mqtt.publishMessage("readings", jsonString);  
}


// Function to publish the device ID 
void publishDeviceID() {
    String deviceID = getDeviceID();  // Get the unique device ID
    unsigned long timestamp = millis(); // Timestamp in milliseconds

    // Create a StaticJsonDocument with a size of 1024 bytes
    StaticJsonDocument<1024> doc;
    doc["device_id"] = deviceID;
    doc["timestamp"] = timestamp;

    // Serialize JSON to a string
    String jsonString;
    serializeJson(doc, jsonString);

    // Publish the device ID to MQTT topic
    mqtt.publishMessage("device_registration", jsonString);  // Topic for device registration
}


void setup() {
    Serial.begin(115200);
    
    // Connect to Wi-Fi
    wifi.connectToWPAEnterprise(wifiSsid, ucsdUsername, ucsdPassword);

    // Connect to the MQTT broker
    if (mqtt.connectToBroker(1883)) {
        // Once connected to the broker, subscribe to a topic (if needed)
        Serial.println("[Main] Connected to MQTT broker");
        mqtt.subscribeTopic("device_registration");  
        mqtt.subscribeTopic("readings");  
    }
    else {
        Serial.println("[Main] Failed to connect to MQTT broker");
    }

    // Set callback function for receiving MQTT messages (if needed)
    mqtt.setCallback([](char* topic, uint8_t* payload, unsigned int length) {
        String message = "";
        for (unsigned int i = 0; i < length; i++) {
            message += (char)payload[i];
        }
        Serial.print("Received message on topic ");
        Serial.print(topic);
        Serial.print(": ");
        Serial.println(message);
    });
    
    // Initialize BMP sensor
    if (!bmp.begin()) {
        Serial.println("Error: BMP sensor not detected!");
        while (1); // Keep trying to find sensor 
    }
}

void loop() {
    mqtt.loop();  // Handle MQTT message processing

    // Periodically publish device ID + Sensor Data (every 5 seconds)
    static unsigned long lastPublishTime = 0;
    unsigned long currentMillis = millis();
    
    if (currentMillis - lastPublishTime >= 5000) { 
        publishDeviceID();
        publishSensorData(); 
        lastPublishTime = currentMillis;
    }
}
