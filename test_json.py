import requests

URL = "http://192.168.1.254:8000/positions.json"
TEAM = 5   # cambia esto si tu team es otro

response = requests.get(URL)
data = response.json()

print("All data:")
print(data)

print("\nYour turret position:")
print(data["turrets"][str(TEAM)])