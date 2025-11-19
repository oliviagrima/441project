from flask import Flask, request, jsonify, render_template
import RPi.GPIO as GPIO
import time
import json
import requests

app = Flask(__name__)

def read_tur_pos(url, id):
    """Download JSON and return turret position for given id."""
    try:
        response = requests.get(url)
        data = response.json()

        turret_data = data["turrets"].get(str(id))
        if turret_data is None:
            return {"error": "team id not found"}

        return {
            "r": turret_data["r"],
            "theta": turret_data["theta"]
        }

    except Exception as e:
        return {"error": str(e)}

def read_target_positions(json_url):
    """Download JSON and return a list of globe positions."""
    try:
        response = requests.get(json_url)
        data = response.json()

        # "globes" is a list in the JSON file
        globes = data.get("globes")

        if globes is None:
            return {"error": "No 'globes' data found in JSON"}

        # Build a clean list of globe coordinates
        target_list = []

        for g in globes:
            target_list.append({
                "r": g["r"],
                "theta": g["theta"],
                "z": g["z"]
            })

        return {"targets": target_list}

    except Exception as e:
        return {"error": str(e)}

@app.route("/read_json", methods=["POST"])
def read_json():
    """Read turret location from JSON file."""
    url = request.json.get("url")
    team = request.json.get("team")

    result = read_tur_pos(url, team)
    return jsonify(result)

@app.route("/read_targets", methods=["POST"])
def read_targets():
    url = request.json.get("url")

    result = read_target_positions(url)
    return jsonify(result)

@app.route("/")
def index():
    return render_template("index.html")
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
