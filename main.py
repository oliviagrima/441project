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

    # ---------------------- 1️⃣ MANUAL MOVE MODE -----------------------
    if "theta" in data or "z" in data:
        try:
            theta_rad = float(data.get("theta", 0))
            z = float(data.get("z", 0))
        except:
            return jsonify({"error": "Invalid manual move inputs"}), 400

        delta_deg = math.degrees(theta_rad)

        if delta_deg != 0:
            zero = load_zero()
            # manual moves are relative to current motor position
            m1.goAngle(m1.angle.value + delta_deg, blocking=True)
        if z != 0:
            m2.goAngle(m2.angle.value + z, blocking=True)

        return jsonify({
            "status": "manual moving",
            "motor1_theta_deg": delta_deg,
            "motor2_z": z
        })

    # ---------------------- 2️⃣ TARGET TRACKING MODE -----------------------
    url = data.get("url")
    team = data.get("team")
    target_id = data.get("target_id")
    target_type = data.get("target_type")

    if not (url and team and target_id and target_type):
        return jsonify({"error": "Missing target move parameters"}), 400

    # --- get your turret position ---
    my_turret = read_tur_pos(url, team)
    if "error" in my_turret:
        return jsonify(my_turret), 400

    r0 = my_turret["r"]
    theta0 = my_turret["theta"]  # arena angle of turret
    z0 = 0

    # --- get all targets ---
    targets_data = read_target_positions(url)
    if "error" in targets_data:
        return jsonify(targets_data), 400

    # --- find target ---
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

    # --- convert to Cartesian ---
    x0 = r0 * math.cos(theta0)
    y0 = r0 * math.sin(theta0)
    xt = rt * math.cos(thetat)
    yt = rt * math.sin(thetat)

    dx = xt - x0
    dy = yt - y0
    dz = zt - z0

    # --- compute rotation needed ---
    target_angle = math.atan2(dy, dx)  # arena delta angle to target
    delta_rad = target_angle - theta0
    delta_rad = (delta_rad + math.pi) % (2 * math.pi) - math.pi
    delta_deg = math.degrees(delta_rad)

    # --- phi conversion ---
    zero = load_zero()
    phi_target = zero.get("phi0", 0) - delta_deg  # arena θ → motor φ
    actual_z = dz + zero.get("z0", 0)
    
    if delta_deg != 0:
        m1.goAngle(m1.angle.value + phi_target, blocking=True)
    if dz != 0:
        m2.goAngle(m2.angle.value + actual_z, blocking=True)

    return jsonify({
        "status": "target moving",
        "motor1_phi_deg": phi,
        "motor2_z": actual_z
    })

@app.route("/set_zero", methods=["POST"])
def set_zero():
    theta_now = m1.angle.value
    z_now = m2.angle.value
    phi_now = 0  # motor pointing toward center
    save_zero(theta_now, z_now, phi_now)


    return jsonify({
        "status": f"Zero set! theta0={theta_now:.2f}, z0={z_now:.2f}"
    })

@app.route("/set_zero", methods=["GET"])
def set_zero_get():
    return jsonify({"error": "Use POST to set zero"}), 405

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
