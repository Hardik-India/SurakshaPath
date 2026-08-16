"""
run_time_slots.py

Generates 4 short SUMO runs at different traffic densities (office / noon /
evening / midnight), matching the real project setup: 3 vehicle types
(car, twowheeler, autorickshaw) defined in vtypes.add.xml, merged into one
route file per slot -- same pattern as the original trips_merged.trips.xml.

Each slot gets its own SSM conflict log: central_kolkata_ssm_<slot>.xml
Your original central_kolkata_ssm.xml / trips_merged.trips.xml are untouched.

Run this from the project folder (same folder as central_kolkata.net.xml,
central_kolkata.sumocfg, vtypes.add.xml).

Usage:
    python run_time_slots.py
"""

import subprocess
import os
import sys

NET_FILE = "central_kolkata.net.xml"
SUMOCFG = "central_kolkata.sumocfg"
VTYPES_FILE = "vtypes.add.xml"

# Sim-time window per slot run, in seconds. The original run was 28800s (8hr);
# we use a shorter window per slot so 4 runs finish today. 1800s = 30 sim-min.
DEMAND_END = 1800

VTYPES = ["car", "twowheeler", "autorickshaw"]

# Period per vtype per slot (seconds between vehicle insertions).
# LOWER period = MORE vehicles = busier road = more conflicts expected.
# Two-wheelers/autos run denser than cars at every slot, matching typical
# Indian traffic mix. Tune after your first run if a slot looks off.
SLOT_PERIODS = {
    "office":   {"car": 1.0, "twowheeler": 0.5, "autorickshaw": 0.8},   # rush hour, dense
    "noon":     {"car": 2.0, "twowheeler": 1.2, "autorickshaw": 1.5},   # moderate midday
    "evening":  {"car": 1.1, "twowheeler": 0.6, "autorickshaw": 0.9},   # rush hour, dense
    "midnight": {"car": 8.0, "twowheeler": 6.0, "autorickshaw": 7.0},   # sparse, quiet
}


def sumo_executable_path():
    """
    Resolve the real sumo.exe path via SUMO_HOME instead of relying on PATH.
    subprocess.run bypasses shell aliases/functions, so if 'sumo' only works
    in the terminal via a shell-level alias (not a true PATH entry), calling
    it by bare name from Python can silently fail to find the right binary.
    """
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        candidate = os.path.join(sumo_home, "bin", "sumo.exe")
        if os.path.exists(candidate):
            return candidate
        candidate_no_ext = os.path.join(sumo_home, "bin", "sumo")
        if os.path.exists(candidate_no_ext):
            return candidate_no_ext
    # Fall back to bare name (works on PATH on most non-Windows setups)
    return "sumo"


def sumo_home_tools_path():
    sumo_home = os.environ.get("SUMO_HOME")
    if not sumo_home:
        print("ERROR: SUMO_HOME environment variable is not set.")
        print("Set it to your SUMO install folder (the one containing 'tools/').")
        sys.exit(1)
    return os.path.join(sumo_home, "tools", "randomTrips.py")


SUMO_EXE = sumo_executable_path()


def generate_demand_for_vtype(slot_name, vtype, period):
    """
    randomTrips.py writes a fixed intermediate file (routes.rou.xml) in the
    CURRENT WORKING DIRECTORY regardless of -o. Running several instances in
    parallel from the same folder makes them collide on that shared filename
    (WinError 32 on Windows). Fix: run each call from its own isolated temp
    subfolder, then move the real output back up to the project folder.
    """
    import shutil
    import tempfile

    trips_file = f"trips_{slot_name}_{vtype}.trips.xml"
    project_dir = os.getcwd()
    net_file_abs = os.path.join(project_dir, NET_FILE)

    with tempfile.TemporaryDirectory(prefix=f"randomtrips_{slot_name}_{vtype}_") as tmpdir:
        tmp_output = os.path.join(tmpdir, trips_file)
        cmd = [
            sys.executable, sumo_home_tools_path(),
            "-n", net_file_abs,
            "-o", tmp_output,
            "--begin", "0",
            "--end", str(DEMAND_END),
            "--period", str(period),
            "--trip-attributes", f'type="{vtype}"',
            "--validate",
        ]
        # Same fix as run_sumo_for_slot: avoid capture_output deadlocks.
        log_path = os.path.join(project_dir, f"randomtrips_log_{slot_name}_{vtype}.txt")
        with open(log_path, "w") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=tmpdir)

        if result.returncode != 0:
            print(f"    ERROR generating {vtype} demand for {slot_name} — see {log_path}")
            return None

        final_path = os.path.join(project_dir, trips_file)
        shutil.move(tmp_output, final_path)

    return trips_file


def merge_trip_files(slot_name, trip_files):
    import xml.etree.ElementTree as ET

    merged_root = ET.Element("routes")
    counter = 0
    all_trips = []

    for tf in trip_files:
        if tf is None or not os.path.exists(tf):
            continue
        tree = ET.parse(tf)
        for trip in tree.getroot().findall("trip"):
            trip.set("id", f"{slot_name}_{counter}")
            all_trips.append(trip)
            counter += 1

    all_trips.sort(key=lambda t: float(t.get("depart", "0")))
    for trip in all_trips:
        merged_root.append(trip)

    merged_file = f"trips_{slot_name}_merged.trips.xml"
    ET.ElementTree(merged_root).write(merged_file, xml_declaration=True, encoding="UTF-8")
    print(f"  Merged {counter} trips across {len(trip_files)} vtypes -> {merged_file}")
    return merged_file


def generate_demand(slot_name, periods):
    print(f"\n--- Generating demand for '{slot_name}' ---")
    trip_files = []
    for vtype in VTYPES:
        period = periods[vtype]
        print(f"  {vtype}: period={period}")
        tf = generate_demand_for_vtype(slot_name, vtype, period)
        trip_files.append(tf)

    if all(tf is None for tf in trip_files):
        print(f"  All vtype generations failed for '{slot_name}'.")
        return None

    return merge_trip_files(slot_name, trip_files)


def run_sumo_for_slot(slot_name, route_file):
    ssm_out = f"central_kolkata_ssm_{slot_name}.xml"
    log_file = f"sumo_log_{slot_name}.txt"
    print(f"\n--- Running SUMO for '{slot_name}' (log: {log_file}) ---")
    print(f"    Using SUMO executable: {SUMO_EXE}")
    cmd = [
        SUMO_EXE, "-c", SUMOCFG,
        "--net-file", NET_FILE,
        "--route-files", route_file,
        "--additional-files", VTYPES_FILE,
        "--begin", "0",
        "--end", str(DEMAND_END),
        "--step-length", "0.5",
        "--device.ssm.probability", "1.0",
        "--device.ssm.file", ssm_out,
        "--device.ssm.measures", "TTC PET DRAC",
        "--device.ssm.thresholds", "3.0 2.0 3.0",
        "--device.ssm.geo", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "90",
    ]
    # IMPORTANT: write stdout/stderr straight to a file instead of capturing
    # in memory. capture_output=True pipes output through Python, and if the
    # child produces more output than the OS pipe buffer holds (a few dozen
    # KB) while Python isn't actively reading it, both processes can stall
    # indefinitely -- this is the likely cause of the earlier hangs.
    with open(log_file, "w") as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=600)

    if result.returncode != 0:
        print(f"  ERROR running SUMO for {slot_name} — see {log_file} for details")
        # Print just the tail so you don't have to open the file for a quick look
        try:
            with open(log_file) as f:
                lines = f.readlines()
            print("  Last 20 lines:")
            for line in lines[-20:]:
                print("   ", line.rstrip())
        except Exception:
            pass
        return None
    print(f"  OK -> {ssm_out}")
    return ssm_out


def process_one_slot(args):
    """Runs demand-gen + SUMO for a single slot, top to bottom. Used by the
    parallel pool -- each slot is fully independent (own files, own process),
    so running 4 at once is safe. Any exception here is caught so one slow
    or broken slot doesn't kill the results already collected for others."""
    slot_name, periods = args
    try:
        route_file = generate_demand(slot_name, periods)
        if route_file is None:
            print(f"[{slot_name}] Skipping SUMO run — demand generation failed.")
            return slot_name, None
        ssm_out = run_sumo_for_slot(slot_name, route_file)
        return slot_name, ssm_out
    except Exception as e:
        print(f"[{slot_name}] FAILED with exception: {e}")
        return slot_name, None


if __name__ == "__main__":
    import multiprocessing

    for required in [NET_FILE, SUMOCFG, VTYPES_FILE]:
        if not os.path.exists(required):
            print(f"ERROR: {required} not found in current folder. Run this from your project folder.")
            sys.exit(1)

    # Skip slots whose SSM output already exists (e.g. from a previous partial
    # run) so re-running after an interruption doesn't waste time redoing work.
    remaining = {}
    for slot_name, periods in SLOT_PERIODS.items():
        existing = f"central_kolkata_ssm_{slot_name}.xml"
        if os.path.exists(existing) and os.path.getsize(existing) > 0:
            print(f"[{slot_name}] {existing} already exists — skipping.")
        else:
            remaining[slot_name] = periods

    if not remaining:
        print("All slots already have SSM output. Nothing to do.")
        sys.exit(0)

    max_workers = min(len(remaining), os.cpu_count() or 4)
    print(f"Running {len(remaining)} remaining slot(s) SEQUENTIALLY (one at a time)...")
    print("(Switched off parallel mode after an unexplained hang during a prior parallel run.)")

    produced = {}
    for slot_name, periods in remaining.items():
        print(f"\n{'='*20} STARTING SLOT: {slot_name} {'='*20}")
        result_slot, ssm_out = process_one_slot((slot_name, periods))
        if ssm_out:
            produced[result_slot] = ssm_out
            print(f"\n>>> [{result_slot}] finished OK -> {ssm_out}\n")
        else:
            print(f"\n>>> [{result_slot}] FAILED\n")

    print("\n" + "=" * 60)
    print("DONE THIS RUN. SSM files produced:")
    for slot, path in produced.items():
        print(f"  {slot:10s} -> {path}")
    missing = set(remaining) - set(produced)
    if missing:
        print(f"\nFailed this run: {sorted(missing)} — check errors above, then re-run the script to retry just these.")
    already_done = set(SLOT_PERIODS) - set(remaining)
    if already_done:
        print(f"\nAlready done (skipped): {sorted(already_done)}")
    print("=" * 60)