import RPi.GPIO as GPIO
import time
import json

with open('data.json', 'r') as file:
    data = json.load(file)

# Team #: 5

# Our position
t_r = data['turrets']['1']['r']
t_theta = data['turrets']['1']['theta']

# Passive target positions
p_r1 = data['globes'][0]['r']
"""
p_theta1 = data['globes']['theta']
p_z1 = data['globes']['z']
p_r2 = data['globes']['r']
p_theta2 = data['globes']['theta']
p_z2 = data['globes']['z']
p_r3 = data['globes']['r']
p_theta3 = data['globes']['theta']
p_z3 = data['globes']['z']
"""
# Step 4: Print the extracted data
print(f"turret radius: {t_r}")
print(f"turret theta: {t_theta}")
print(f"target 1 r: {p_r1}")
"""
print(f"target 1 theta: {p_theta1}")
print(f"target 1 z: {p_z1}")
print(f"target 2 r: {p_r2}")
print(f"target 2 theta: {p_theta2}")
print(f"target 2 z: {p_z2}")
print(f"target 3 r: {p_r3}")
print(f"target 3 theta: {p_theta3}")
print(f"target 3 z: {p_z3}")
"""
