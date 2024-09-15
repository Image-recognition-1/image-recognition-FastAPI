import requests
import json

def search_nearby(api_key, latitude, longitude, radius=500.0, max_result_count=10):
    url = 'https://places.googleapis.com/v1/places:searchNearby'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'places.displayName'
    }
    payload = {
        "includedTypes": [
            "electric_vehicle_charging_station"
        ],
        "maxResultCount": max_result_count,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": radius
            }
        }
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None


api_key = 'AIzaSyBo7u5Z2yJOZJSoP2ZwDEFYUSJ4hvNybmY'
latitude = 59.3293
longitude = 18.0686
radius = 500.0

result = search_nearby(api_key, latitude, longitude, radius)
if result:
    print(result)
