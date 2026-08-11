import xml.etree.ElementTree as ET

file_type_map = {
    "trips_car.trips.xml": "car",
    "trips_2w.trips.xml": "twowheeler",
    "trips_auto.trips.xml": "autorickshaw",
}

all_trips = []

for filename, vtype in file_type_map.items():
    tree = ET.parse(filename)
    root = tree.getroot()
    for trip in root.findall("trip"):
        trip.set("type", vtype)   # inject the vehicle type here, safely, no shell involved
        all_trips.append(trip)

# Sort by depart time so SUMO doesn't complain about unsorted routes
all_trips.sort(key=lambda t: float(t.get("depart")))

# Reassign unique IDs to avoid collisions across the three files
for i, trip in enumerate(all_trips):
    trip.set("id", str(i))

root_out = ET.Element("routes")
for trip in all_trips:
    root_out.append(trip)

tree_out = ET.ElementTree(root_out)
tree_out.write("trips_merged.trips.xml", encoding="UTF-8", xml_declaration=True)
print(f"Merged {len(all_trips)} trips into trips_merged.trips.xml")