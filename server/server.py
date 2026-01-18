"""
Flask Server for VibeSense
==========================
Receives biometric data (pulse and breathing averages) from iOS app
and processes it for the emotion detection system.

Run with: python server.py
"""

# get data from main.py (emotions) in the past 5 seconds. 
# get data from biometrics endpoint
# put all these in the prompt to gemini api

import os
from dotenv import load_dotenv
from google import genai
from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# Store the latest biometric data
latest_biometrics = {
    "pulse_average": None,
    "breathing_average": None,
    "timestamp": None
}


@app.route('/biometrics', methods=['POST'])
def receive_biometrics():
    """
    POST endpoint to receive biometric data from Swift app.
    
    Expected JSON format:
    {
        "pulse_average": float,
        "breathing_average": float
    }
    """
    try:
        data = request.get_json()
        
        if data is None:
            return jsonify({
                "status": "error",
                "message": "No JSON data received"
            }), 400
        
        # Validate required fields
        if "pulse_average" not in data or "breathing_average" not in data:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: pulse_average and breathing_average"
            }), 400
        
        # Extract and validate the values
        pulse_avg = data.get("pulse_average")
        breathing_avg = data.get("breathing_average")
        
        # Validate types (should be numeric)
        if not isinstance(pulse_avg, (int, float)) or not isinstance(breathing_avg, (int, float)):
            return jsonify({
                "status": "error",
                "message": "pulse_average and breathing_average must be numeric values"
            }), 400
        
        # Update the latest biometrics
        latest_biometrics["pulse_average"] = float(pulse_avg)
        latest_biometrics["breathing_average"] = float(breathing_avg)
        latest_biometrics["timestamp"] = datetime.now().isoformat()
        
        print(f"[{latest_biometrics['timestamp']}] Received biometrics - "
              f"Pulse: {pulse_avg}, Breathing: {breathing_avg}")
        
        return jsonify({
            "status": "success",
            "message": "Biometric data received",
            "data": {
                "pulse_average": pulse_avg,
                "breathing_average": breathing_avg,
                "timestamp": latest_biometrics["timestamp"]
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
        
load_dotenv()  # ensure .env is read when running locally

def _get_genai_client():
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("api_key")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY (or api_key) environment variable for Gemini.")
    return genai.Client(api_key=api_key)

@app.route('/gemini', methods=['POST'])
def call_gemini():
    """
    POST endpoint to proxy a Gemini text request.
    Expected JSON: { "prompt": "text to send to Gemini" }
    """
    try:
        data = request.get_json() or {}
        prompt = data.get("prompt")
        if not prompt:
            return jsonify({
                "status": "error",
                "message": "Missing required field: prompt"
            }), 400

        client = _get_genai_client()
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )

        return jsonify({
            "status": "success",
            "response": getattr(response, "text", None)
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    print("=" * 50)
    print("VibeSense Flask Server")
    print("=" * 50)
    print("\nEndpoints:")
    print("  POST /biometrics - Send pulse and breathing data")
    print("  GET  /biometrics - Get latest biometric data")
    print("  GET  /health     - Health check")
    print("  GET  /gemini     - Gemini")
    print("\n" + "=" * 50)
    
    # Run on all interfaces so iOS device can connect
    # Use port 8080 by default
    app.run(host='0.0.0.0', port=8080, debug=True)
