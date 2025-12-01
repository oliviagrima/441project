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

"""delete later"""
"""
positions_data = {
    "turrets": {
        "1": {"r": 300.0, "theta": 1.5882496193148399},
        "2": {"r": 300.0, "theta": 5.7246799465414},
        "3": {"r": 300.0, "theta": 4.572762640225144},
        "4": {"r": 300.0, "theta": 0.41887902047863906},
        "5": {"r": 300.0, "theta": 0.017453292519943295},
        "6": {"r": 300.0, "theta": 0.6981317007977318},
        "7": {"r": 300.0, "theta": 5.794493116621174},
        "8": {"r": 300.0, "theta": 3.211405823669566},
        "9": {"r": 300.0, "theta": 5.8643062867009474},
        "10": {"r": 300.0, "theta": 2.007128639793479},
        "11": {"r": 300.0, "theta": 5.427973973702365},
        "12": {"r": 300.0, "theta": 0.890117918517108},
        "13": {"r": 300.0, "theta": 1.4835298641951802},
        "14": {"r": 300.0, "theta": 3.385938748868999},
        "15": {"r": 300.0, "theta": 0.7853981633974483},
        "16": {"r": 300.0, "theta": 3.036872898470133},
        "17": {"r": 300.0, "theta": 1.2915436464758039},
        "18": {"r": 300.0, "theta": 1.117010721276371},
        "19": {"r": 300.0, "theta": 0.017453292519943295},
        "20": {"r": 300.0, "theta": 5.026548245743669}
    },
    "globes": [
        {"r": 300.0, "theta": 3.385938748868999, "z": 103.0},
        {"r": 300.0, "theta": 6.19591884457987, "z": 16.0},
        {"r": 300.0, "theta": 1.2740903539558606, "z": 172.0},
        {"r": 300.0, "theta": 0.8203047484373349, "z": 197.0},
        {"r": 300.0, "theta": 5.654866776461628, "z": 90.0},
        {"r": 300.0, "theta": 1.0297442586766543, "z": 35.0},
        {"r": 300.0, "theta": 4.852015320544236, "z": 118.0},
        {"r": 300.0, "theta": 1.902408884673819, "z": 139.0}
    ]
}
"""

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
    """Download JSON and return a list of all targets: globes + other turrets."""
    try:
        response = requests.get(url)
        data = response.json()

        targets = []

        # Agregar globes
        for g in data.get("globes", []):
            targets.append({
                "type": "globe",
                "theta": g["theta"],
                "r": g["r"],
                "z": g.get("z", 0)
            })

        # Agregar turrets (oponentes)
        for tid, tdata in data.get("turrets", {}).items():
            targets.append({
                "type": "turret",
                "theta": tdata["theta"],
                "r": tdata["r"],
                "id": tid
            })

        return {"targets": targets}

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

@app.route("/my_turret", methods=["POST"])
def my_turret():
    url = request.json.get("url")
    team_id = request.json.get("team")

    if not url or not team_id:
        return jsonify({"error": "Provide JSON URL and your team ID"}), 400

    try:
        response = requests.get(url)
        data = response.json()
        turret_data = data["turrets"].get(str(team_id))

        if not turret_data:
            return jsonify({"error": "Team ID not found"}), 404

        return jsonify({
            "r": turret_data["r"],
            "theta": turret_data["theta"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import math

@app.route("/move_motor", methods=["POST"])
def move_motor():
    try:
        theta_rad = float(request.json.get("theta", 0))
        z = float(request.json.get("z", 0))
    except Exception as e:
        return jsonify({"error": f"Invalid input: {e}"}), 400

    # Convert theta from radians → degrees
    angle_theta = math.degrees(theta_rad)

    if angle_theta != 0:
        m1.goAngle(m1.angle.value + angle_theta, blocking=True)
    if z != 0:
        m2.goAngle(m2.angle.value + z, blocking=True)

    return jsonify({
        "status": "moving",
        "motor1_theta": angle_theta,
        "motor2_z": z
    })

"""delete later"""
"""
@app.route("/positions.json")
def positions():
    return jsonify(positions_data)
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
