import urllib.request
import urllib.error
import json

base_url = "http://localhost:8000"

def request(method, path, data=None, token=None):
    url = base_url + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    req = urllib.request.Request(url, method=method, headers=headers)
    if data:
        req.data = json.dumps(data).encode("utf-8")
        
    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode()
            try:
                return json.loads(res_data)
            except:
                return res_data
    except urllib.error.HTTPError as e:
        return f"HTTP Error {e.code}: {e.read().decode()}"
    except Exception as e:
        return f"Error: {e}"

print("1. Register ambulance user")
print(request("POST", "/api/auth/register", {"email": "amb1@test.com", "password": "test123", "role": "ambulance"}))

print("\n2. Register hospital user")
print(request("POST", "/api/auth/register", {"email": "hosp1@test.com", "password": "test123", "role": "hospital", "hospital_id": 1}))

print("\n3. Login as ambulance")
amb_login = request("POST", "/api/auth/login", {"email": "amb1@test.com", "password": "test123"})
print(amb_login)
amb_token = amb_login.get("access_token") if isinstance(amb_login, dict) else None

print("\n4. Get hospitals")
print(request("GET", "/api/hospitals"))

print("\n5. Login as hospital")
hosp_login = request("POST", "/api/auth/login", {"email": "hosp1@test.com", "password": "test123"})
print(hosp_login)
hosp_token = hosp_login.get("access_token") if isinstance(hosp_login, dict) else None

print("\n6. Update hospital availability")
print(request("PUT", "/api/hospitals/1/availability", {"beds": 8, "icu": 2, "doctors": 4, "equipment": ["ecg", "ventilator"], "accepting": True}, hosp_token))

print("\n7. Get hospitals again")
print(request("GET", "/api/hospitals"))

print("\n8. Dispatch")
print(request("POST", "/api/dispatch", {"condition": "cardiac arrest", "equipment_needed": ["ecg"], "ambulance_lat": 28.6139, "ambulance_lng": 77.2090}, amb_token))
