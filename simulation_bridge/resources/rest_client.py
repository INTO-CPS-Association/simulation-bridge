import requests
import yaml
import json
import threading
import logging
import time
import os
from flask import Flask, request, jsonify

# Config
BRIDGE_URL = "http://localhost:5000/message"  # Send message here
CLIENT_PORT = 5001                             # This client listens here
RESULTS_ENDPOINT = "/result"                  # For receiving results

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RESTClient")

# Flask app
app = Flask(__name__)
received_results = []

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"})

@app.route(RESULTS_ENDPOINT, methods=['POST'])
def receive_result():
    try:
        data = request.get_json(force=True)
        received_results.append(data)
        logger.info(f"✅ Received result: {json.dumps(data, indent=2)}")
        return jsonify({"status": "received"}), 200
    except Exception as e:
        logger.error(f"Error parsing result: {e}")
        return jsonify({"error": str(e)}), 400

def start_client_receiver():
    """Start Flask server in a separate thread"""
    logger.info(f"🚀 Starting result receiver on http://localhost:{CLIENT_PORT}{RESULTS_ENDPOINT}")
    app.run(host="localhost", port=CLIENT_PORT, debug=False, use_reloader=False)

def wait_until_ready(url, timeout=30):
    for _ in range(timeout):
        try:
            if requests.get(url).status_code == 200:
                logger.info("🔗 Bridge is ready.")
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    logger.error("❌ Bridge did not respond in time.")
    return False

def send_test_message():
    """Send a test simulation message to the bridge"""
    path = os.path.join(os.path.dirname(__file__), "simulation.yaml")
    try:
        with open(path, "r") as f:
            payload = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"❌ Failed to read simulation.yaml: {e}")
        return

    response = requests.post(
        BRIDGE_URL,
        data=yaml.dump(payload),
        headers={"Content-Type": "application/x-yaml"}
    )
    logger.info(f"📨 Sent message. Status: {response.status_code}")
    logger.info(f"📝 Response: {response.text}")

if __name__ == "__main__":
    # Start result receiver
    threading.Thread(target=start_client_receiver, daemon=True).start()

    send_test_message()

    # Keep alive to receive results
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        logger.info("👋 Client stopped.")
