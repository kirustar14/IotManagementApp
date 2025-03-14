import paho.mqtt.client as mqtt
import json
from datetime import datetime
import requests
import time
from dotenv import load_dotenv
import os

# Global variable to store the latest device_id
latest_device_id = None

# MQTT Broker settings
BROKER = "broker.hivemq.com"
PORT = 1883
BASE_TOPIC = "abc/ece140/devices"
TOPIC1 = BASE_TOPIC + "/device_registration"
API_URL1 = "http://localhost:8000/api/register_device1"

TOPIC2 = BASE_TOPIC + "/readings"
WEB_SERVER_URL = "http://localhost:8000/api/temperature"
# To track the last time we sent a POST request
last_post_time = 0



def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker."""
    if rc == 0:
        print("Successfully connected to MQTT broker")
        client.subscribe(TOPIC1)
        client.subscribe(TOPIC2)
        print(f"Subscribed to {TOPIC1}")
        print(f"Subscribed to {TOPIC2}")
    else:
        print(f"Failed to connect with result code {rc}")

# sending temperature data to server 
def send_temperature_to_server(temperature, timestamp):
    """Send temperature data to the web server via a POST request."""
    global last_post_time
    current_time = time.time()
    if timestamp=="N/A":
        timestamp= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Only send the request every 5 seconds
    if current_time - last_post_time >= 5:
        data = {
            "value": temperature,
            "unit": "C",
            "timestamp": timestamp
        }

        try:
            print(data)
            response = requests.post(WEB_SERVER_URL, json=data) 
            if response.status_code == 200:
                print(f"Temperature data sent successfully: {data}")
            else:
                print(f"Failed to send data. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error sending data to server: {e}") 
        
        last_post_time = current_time  # Update the last_post_time to the current time


# Callback when message is received from MQTT
def on_message(client, userdata, msg):
    global latest_device_id  # Access global variable

    try:
        # Parse JSON message
        payload = json.loads(msg.payload.decode())
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp = current_time

        if msg.topic == TOPIC2:
            temperature = payload.get("temperature", "N/A")

            print(f"\n[{current_time}] Sensor Reading:")
            print(f"  - Temperature: {temperature} °C")
            print(f"  - ESP32 Timestamp: {timestamp} ms")

            # Send the temperature data to the web server
            if temperature != "N/A":
                send_temperature_to_server(temperature, timestamp)
        
        if msg.topic == TOPIC1: 
            device_id = payload.get("device_id", latest_device_id)
            if not device_id:  # Ensure device_id is valid
                print("Error: device_id is missing or empty")
            
            # Save the device_id for later use
            latest_device_id = device_id

            # Send data to FastAPI server
            data = {
                "device_id": device_id,
            }

            # POST request to FastAPI
            response = requests.post(API_URL1, json=data) 
            
            if response.status_code == 200:
                print("Device id sent succesfully")
            else:
                print(latest_device_id)
                print(data)
                print(f"Failed to send device id. Status code: {response.status_code}")

    except json.JSONDecodeError:
        print(f"Received non-JSON message on {msg.topic}:")
        print(f"Payload: {msg.payload.decode()}")

def main():
    # Create MQTT client
    print("Creating MQTT client...")
    client = mqtt.Client()

    # Set callback functions
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        # Connect to broker
        print("Connecting to broker...")
        client.connect(BROKER, PORT, 60)

        # Start the MQTT loop
        print("Starting MQTT loop...")
        client.loop_forever()

    except KeyboardInterrupt:
        print("\nDisconnecting from broker...")
        client.disconnect()
        print("Exited successfully")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
