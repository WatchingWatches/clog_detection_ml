import csv
import time
import json
import requests
import math
import os

# Klipper API endpoint (update IP and port if needed) (Moonraker API)
url = "http://localhost:7125/printer/objects/query?extruder&motion_report&print_stats" # locally on rpi
#url = 'http://192.168.178.112:7125/printer/objects/query?extruder&motion_report&print_stats' # edit the ip adress to your machine 

# CSV file setup
# Generate a new file name containing the time and date
current_time = time.strftime("%Y%m%d-%H%M%S")
file_name = f"sensor_data_{current_time}"

disconnect = False

# Calculate filament cross-sectional area (in mm²)
filament_area = math.pi * (1.75 / 2) ** 2
# Create 'data' directory if it does not exist
if not os.path.exists('data'):
    os.makedirs('data')
# CSV file setup
with open(os.path.join('data', file_name + '.csv'), "w", newline="") as csvfile:
    fieldnames = ["timestamp","delta_T", "extruder_power", "volumetric_flow"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    print("Script running")
    try:
        response = requests.get(url).json()
        result = response["result"]["status"]

        print_file = result['print_stats']['filename']
        print_temperature = result["extruder"]["target"]
        print_time = result['print_stats']['total_duration']

        with open(os.path.join('data', file_name + '.json'), 'w') as jsonfile:
                json.dump({"setup": {"print_file": print_file,
                                     "print_temperature": print_temperature,
                                     "print_time": print_time,
                                     "print_end_status": "undifined"
                                     }}, jsonfile, indent = 2)
        written_json = True

    except Exception as e:
        print(f"Error writing metadata: {e}")
        print('Writing metadata failed.')
        written_json = False

    failed_connection_n = 0
    while True:
        try:
            # Query data from Klipper via Moonraker API
            response = requests.get(url).json()
            result = response["result"]["status"]

            if disconnect:
                print('Measurement started again.')
                disconnect = False
                failed_connection_n = 0
            
            delta_T = round(result["extruder"]["target"] - result["extruder"]["temperature"], 3)
            # Extract extruder power
            extruder_power = result["extruder"]["power"] * 100  # Convert to percentage

            # Extract extruder speed for flow rate calculation
            extruder_speed_mm_s = result["motion_report"]["live_extruder_velocity"]  # in mm/s

            if extruder_speed_mm_s < 0:
                extruder_speed_mm_s = 0 # retraction

            # Calculate volumetric flow rate (mm³/s)
            volumetric_flow = filament_area * extruder_speed_mm_s
            time_api = response["result"]["eventtime"]
            # Prepare data row
            data = {
                "timestamp": time_api,
                "delta_T": delta_T,
                "extruder_power": extruder_power,
                "volumetric_flow": volumetric_flow
            }

            print_state = result['print_stats']['state']
            if  print_state != "printing":
                if print_state == "paused":
                    time.sleep(1)
                    continue # don't write data
                print("Print ended.")
                break

            # Write to CSV
            writer.writerow(data)
            time.sleep(1)  # Query interval in seconds
            
        except requests.exceptions.RequestException as e:
            failed_connection_n += 1
            if not disconnect:
                print(f"Error querying Klipper API: {e}")
            disconnect = True
            time.sleep(5)  # Wait before retrying
            # break after 30 minutes
            if failed_connection_n * 5 == 30 * 60:
                break

if written_json:
    # write end state of print to json file
    with open(os.path.join('data', file_name + '.json'), 'r+') as jsonfile:
        data = json.load(jsonfile)
        data["setup"]["print_end_status"] = print_state
        jsonfile.seek(0)
        json.dump(data, jsonfile, indent=2)
        jsonfile.truncate()
    