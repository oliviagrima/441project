from flask import Flask, request, jsonify, render_template
from motor_move import Stepper
from shifter import Shifter
import multiprocessing
import RPi.GPIO as GPIO
import time
import json
import math
import requests
import atexit
import os

app = Flask(__name__)

# Global placeholders for hardware objects
s = None
m1 = None
m2 = None
lock1 = multiprocessing.Lock()
lock2 = multiprocessing.Lock()

# Initialize hardware safely
def init_hardware():
    global s, m1, m2
    try:
        GPIO.setwarnings(False)
        GPIO.cleanup()  # free any leftover pins from previous runs
        GPIO.setmode(GPIO.BCM)
        s = Shifter(data=16, latch=20,clock=21 )
        m1 = Stepper(s, lock1)
        m2 = Stepper(s, lock2)
        m1.zero()
        m2.zero()
    except Exception as e:
        print("Error initializing hardware:", e)
        GPIO.cleanup()  # ensure pins are freed
        raise

# Cleanup GPIO on exit
def cleanup_hardware():
    GPIO.cleanup()

atexit.register(cleanup_hardware)

def load_positions():
    path = os.path.join(os.path.dirname(__file__), "positions.json")
    with open(path, "r") as f:
        return json.load(f)

ZERO_FILE = os.path.join(os.path.dirname(__file__), "zero.json")

def load_zero():
    try:
        with open(ZERO_FILE, "r") as f:
            return json.load(f)
    except:
        return {"theta0": 0, "z0": 0}

def save_zero(theta0, z0):
    with open(ZERO_FILE, "w") as f:
        json.dump({"theta0": theta0, "z0": z0}, f, indent=4)

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

@app.route("/move_motor", methods=["POST"])
def move_motor():
    data = request.json

    # Manual move mode
    if "phi" in data or "z" in data:
        try:
            phi = float(data.get("phi", 0))  # laser rotation
            z = float(data.get("z", 0))
        except:
            return jsonify({"error": "Invalid manual move inputs"}), 400

        if abs(phi) > 0:
            m1.goAngle(m1.angle.value + phi, blocking=True)
        if abs(z) > 0:
            m2.goAngle(m2.angle.value + z, blocking=True)

        return jsonify({
            "status": "manual moving",
            "motor1_phi": phi,
            "motor2_z": z
        })

    # Target tracking mode
    url = data.get("url")
    team = data.get("team")
    target_id = data.get("target_id")
    target_type = data.get("target_type")

    if not (url and team and target_id and target_type):
        return jsonify({"error": "Missing target move parameters"}), 400

    # Load turret position
    my_turret = read_tur_pos(url, team)
    if "error" in my_turret:
        return jsonify(my_turret), 400

    r0 = my_turret["r"]       # turret radius
    theta0 = my_turret["theta"]  # turret fixed angle
    z0 = 0

    # Load targets
    targets_data = read_target_positions(url)
    if "error" in targets_data:
        return jsonify(targets_data), 400

    # Find target
    target = None
    for t in targets_data["targets"]:
        if target_type == "turret" and t.get("id") == target_id:
            target = t
            break
        if target_type == "globe" and t.get("theta") == float(target_id):
            target = t
            break

    if not target:
        return jsonify({"error": "Target not found"}), 400

    rt = target["r"]
    thetat = target["theta"]
    zt = target.get("z", 0)

    # Load zero offsets
    zero = load_zero()  # expects {"phi0": ..., "z0": ...}

    # Compute vector from turret to target
    dx = rt * math.cos(thetat) - r0 * math.cos(theta0)
    dy = rt * math.sin(thetat) - r0 * math.sin(theta0)

    # Vector from turret to center
    dx_center = -r0 * math.cos(theta0)
    dy_center = -r0 * math.sin(theta0)

    # Angle between turret-to-center and turret-to-target
    phi_target = math.atan2(dy, dx) - math.atan2(dy_center, dx_center)
    phi_deg = math.degrees(phi_target) + zero.get("phi0", 0)

    # Vertical movement
    dz = zt - z0 + zero.get("z0", 0)

    # Move motors
    if abs(phi_deg) > 0.01:
        m1.goAngle(m1.angle.value + phi_deg, blocking=True)
    if abs(dz) > 0.01:
        m2.goAngle(m2.angle.value + dz, blocking=True)

    return jsonify({
        "status": "target moving",
        "motor1_phi_deg": phi_deg,
        "motor2_z": dz
    })

@app.route("/set_zero", methods=["POST"])
def set_zero():
    try:
        theta_now = m1.angle.value
        z_now = m2.angle.value
        save_zero(theta_now, z_now)
        return jsonify({"status": f"Zero set! theta0={theta_now:.2f}, z0={z_now:.2f}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/go_zero", methods=["POST"])
def go_zero():
    zero = load_zero()
    phi_zero = zero.get("phi0", 0)
    z_zero = zero.get("z0", 0)
    m1.goAngle(phi_zero, blocking=True)
    m2.goAngle(z_zero, blocking=True)
    return jsonify({"status": "moved to zero", "phi_zero": phi_zero, "z_zero": z_zero})

@app.route("/positions.json")
def positions():
    return jsonify(load_positions())

if __name__ == "__main__":
    try:
        init_hardware()
        app.run(host="0.0.0.0", port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nCtrl+C pressed — cleaning up GPIO and exiting.")
        GPIO.cleanup()
    except Exception as e:
        print("Error:", e)
        GPIO.cleanup()
