from flask import Flask, request, jsonify, render_template
from motor_move import Stepper
from shifter import Shifter
import multiprocessing
import RPi.GPIO as GPIO
import time
import json
import requests

app = Flask(__name__)

s = Shifter(data=16, latch=20, clock=21)

lock1 = multiprocessing.Lock()
lock2 = multiprocessing.Lock()

m1 = Stepper(s, lock1)
m2 = Stepper(s, lock2)

m1.zero()
m2.zero()

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

def read_target_positions(url):
    """Download JSON and return a list of globe positions."""
    try:
        response = requests.get(url)
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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/read_json", methods=["POST"])
def read_json():
    url = request.json.get("url")
    team = request.json.get("team")

    result = read_tur_pos(url, team)
    return jsonify(result)

@app.route("/read_targets", methods=["POST"])
def read_targets():
    url = request.json.get("url")

    result = read_target_positions(url)
    return jsonify(result)

@app.route("/my_turret", methods=["GET"])
def my_turret():
    with m1.angle.get_lock():
        return jsonify({"theta": m1.angle.value})

@app.route("/move_motor", methods=["POST"])
def move_motor():
    angle = request.json.get("angle")

    if angle is None:
        return jsonify({"error": "No angle provided"}), 400

    # Motor 1 rotates theta
    m1.goAngle(angle)

    return jsonify({"status": "moving", "motor": 1, "angle": angle})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
