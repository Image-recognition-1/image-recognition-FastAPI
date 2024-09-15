import requests

def fetch_charging_stations(api_key, latitude, longitude, distance_km=10, max_results=10):
    url = "https://api.openchargemap.io/v3/poi/"
    params = {
        "output": "json",
        "latitude": latitude,
        "longitude": longitude,
        "distance": distance_km,
        "maxresults": max_results,
        "key": api_key
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status() 
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching charging stations: {e}")
        return []

def print_charging_stations(stations):
    for station in stations:
        address_info = station.get("AddressInfo", {})
        title = address_info.get("Title", "Unknown Title")
        address = address_info.get("AddressLine1", "Unknown Address")
        distance = station.get("AddressInfo", {}).get("Distance", "Unknown")
        location = station.get("AddressInfo", {}).get("Latitude", "Unknown"), station.get("AddressInfo", {}).get("Longitude", "Unknown")
        print(f"Title: {title}")
        print(f"Address: {address}")
        print(f"Distance: {distance} km")
        print(f"Location: {location}")
        print("-" * 40)

api_key = "9352ac4f-a86b-4793-bc32-b833f9d33976"

# # Stockholm
# latitude = 59.3293
# longitude = 18.0686

# Mostar
latitude = 43.3417392
longitude = 17.8019694

charging_stations = fetch_charging_stations(api_key, latitude, longitude)

print_charging_stations(charging_stations)
