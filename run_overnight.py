import traci
import csv
import os

SUMO_CFG = "central_kolkata.sumocfg"
AGGREGATION_INTERVAL = 60
STOP_FLAG_FILE = "STOP_SIMULATION"
SSM_OUTPUT_FILE = "central_kolkata_ssm.xml"
SPEEDING_OVERAGE = 1.10
HARD_BRAKE_THRESHOLD = -3.0   # m/s^2

sumo_cmd = [
    "sumo", "-c", SUMO_CFG,
    "--step-length", "0.5",
    "--device.ssm.probability", "1.0",
    "--device.ssm.file", SSM_OUTPUT_FILE,
    "--device.ssm.measures", "TTC PET DRAC",
    "--device.ssm.thresholds", "3.0 2.0 3.0",
    "--device.ssm.geo", "true",
    "--no-warnings", "true"
]

traci.start(sumo_cmd)

lane_file_exists = os.path.exists("lane_dataset.csv") and os.stat("lane_dataset.csv").st_size > 0
lane_csv = open("lane_dataset.csv", "a", newline="", buffering=1)
lane_writer = csv.writer(lane_csv)
if not lane_file_exists:
    lane_writer.writerow([
        "window_start", "window_end", "lane_id", "edge_id",
        "vehicle_count", "mean_speed_ms", "max_speed_observed_ms",
        "halting_count", "occupancy_pct", "speed_limit_ms",
        "mean_gap_m", "min_gap_m", "mean_rel_velocity_ms",
        "mean_time_gap_s", "min_time_gap_s",
        "mean_acceleration_ms2", "min_acceleration_ms2", "hard_brake_count"
    ])

speed_file_exists = os.path.exists("speeding_events.csv") and os.stat("speeding_events.csv").st_size > 0
speed_csv = open("speeding_events.csv", "a", newline="", buffering=1)
speed_writer = csv.writer(speed_csv)
if not speed_file_exists:
    speed_writer.writerow(["time", "vehicle_id", "vehicle_type", "lane_id", "speed_ms", "speed_limit_ms", "pct_over"])

all_lane_ids = traci.lane.getIDList()
max_speed_tracker = {lane: 0.0 for lane in all_lane_ids}
gap_tracker = {lane: [] for lane in all_lane_ids}
rel_velocity_tracker = {lane: [] for lane in all_lane_ids}
time_gap_tracker = {lane: [] for lane in all_lane_ids}
accel_tracker = {lane: [] for lane in all_lane_ids}
hard_brake_count = {lane: 0 for lane in all_lane_ids}

next_agg_time = AGGREGATION_INTERVAL
window_start = 0
step_count = 0

print("Simulation started. Logging to lane_dataset.csv and speeding_events.csv")
print(f"To stop gracefully, create a file named '{STOP_FLAG_FILE}' in this folder.")

while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
    t = traci.simulation.getTime()
    step_count += 1

    for veh_id in traci.vehicle.getIDList():
        lane_id = traci.vehicle.getLaneID(veh_id)
        if not lane_id or lane_id not in max_speed_tracker:
            continue

        speed = traci.vehicle.getSpeed(veh_id)
        if speed > max_speed_tracker[lane_id]:
            max_speed_tracker[lane_id] = speed

        limit = traci.lane.getMaxSpeed(lane_id)
        if speed > limit * SPEEDING_OVERAGE:
            veh_type = traci.vehicle.getTypeID(veh_id)
            pct_over = (speed / limit - 1) * 100
            speed_writer.writerow([round(t, 1), veh_id, veh_type, lane_id, round(speed, 2), round(limit, 2), round(pct_over, 1)])

        accel = traci.vehicle.getAcceleration(veh_id)
        accel_tracker[lane_id].append(accel)
        if accel < HARD_BRAKE_THRESHOLD:
            hard_brake_count[lane_id] += 1

        leader_info = traci.vehicle.getLeader(veh_id, 100.0)
        if leader_info is not None:
            leader_id, gap_distance = leader_info
            if gap_distance >= 0:
                leader_speed = traci.vehicle.getSpeed(leader_id)
                rel_velocity = speed - leader_speed
                gap_tracker[lane_id].append(gap_distance)
                rel_velocity_tracker[lane_id].append(rel_velocity)
                if speed > 0.1:
                    time_gap = gap_distance / speed
                    time_gap_tracker[lane_id].append(time_gap)

    if t >= next_agg_time:
        for lane_id in all_lane_ids:
            veh_count = traci.lane.getLastStepVehicleNumber(lane_id)
            if veh_count == 0 and max_speed_tracker[lane_id] == 0.0:
                continue

            mean_speed = traci.lane.getLastStepMeanSpeed(lane_id)
            halting = traci.lane.getLastStepHaltingNumber(lane_id)
            occupancy = traci.lane.getLastStepOccupancy(lane_id)
            speed_limit = traci.lane.getMaxSpeed(lane_id)

            gaps = gap_tracker[lane_id]
            rels = rel_velocity_tracker[lane_id]
            tgaps = time_gap_tracker[lane_id]
            accels = accel_tracker[lane_id]

            mean_gap = round(sum(gaps) / len(gaps), 2) if gaps else ""
            min_gap = round(min(gaps), 2) if gaps else ""
            mean_rel_vel = round(sum(rels) / len(rels), 2) if rels else ""
            mean_time_gap = round(sum(tgaps) / len(tgaps), 2) if tgaps else ""
            min_time_gap = round(min(tgaps), 2) if tgaps else ""
            mean_accel = round(sum(accels) / len(accels), 2) if accels else ""
            min_accel = round(min(accels), 2) if accels else ""

            lane_writer.writerow([
                window_start, round(t, 1), lane_id, lane_id.rsplit("_", 1)[0],
                veh_count, round(mean_speed, 2), round(max_speed_tracker[lane_id], 2),
                halting, round(occupancy, 2), round(speed_limit, 2),
                mean_gap, min_gap, mean_rel_vel,
                mean_time_gap, min_time_gap,
                mean_accel, min_accel, hard_brake_count[lane_id]
            ])

        max_speed_tracker = {lane: 0.0 for lane in all_lane_ids}
        gap_tracker = {lane: [] for lane in all_lane_ids}
        rel_velocity_tracker = {lane: [] for lane in all_lane_ids}
        time_gap_tracker = {lane: [] for lane in all_lane_ids}
        accel_tracker = {lane: [] for lane in all_lane_ids}
        hard_brake_count = {lane: 0 for lane in all_lane_ids}
        window_start = t
        next_agg_time += AGGREGATION_INTERVAL
        print(f"[t={t:.0f}s] Logged lane window. Active vehicles: {traci.vehicle.getIDCount()}")

    if step_count % 1000 == 0 and os.path.exists(STOP_FLAG_FILE):
        print(f"Stop flag detected at sim-time {t:.0f}s. Shutting down cleanly.")
        break

lane_csv.close()
speed_csv.close()
traci.close()
print("Simulation ended. Files closed safely.")