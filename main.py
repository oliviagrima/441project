import RPi.GPIO as GPIO
import time
import json

with open('data.json', 'r') as file:
    data = json.load(file)

r1 = data['turrets']['1']['r']

# Step 4: Print the extracted data
print(f"radius: {r1}")
