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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

"""
with open('data.json', 'r') as file:
    data = json.load(file)


# Team #: 5
# Our position
t_r = data['turrets']['1']['r']
t_theta = data['turrets']['1']['theta']

# Passive target positions
p_r1 = data['globes'][0]['r']
p_theta1 = data['globes'][0]['theta']
p_z1 = data['globes'][0]['z']
p_r2 = data['globes'][1]['r']
p_theta2 = data['globes'][1]['theta']
p_z2 = data['globes'][1]['z']
p_r3 = data['globes'][2]['r']
p_theta3 = data['globes'][2]['theta']
p_z3 = data['globes'][2]['z']

# Step 4: Print the extracted data
print(f"turret radius: {t_r}")
print(f"turret theta: {t_theta}")
print(f"target 1 r: {p_r1}")

print(f"target 1 theta: {p_theta1}")
print(f"target 1 z: {p_z1}")
print(f"target 2 r: {p_r2}")
print(f"target 2 theta: {p_theta2}")
print(f"target 2 z: {p_z2}")
print(f"target 3 r: {p_r3}")
print(f"target 3 theta: {p_theta3}")
print(f"target 3 z: {p_z3}")
"""