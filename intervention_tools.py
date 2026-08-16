import sumolib
import xml.etree.ElementTree as ET
import subprocess
import os

def get_connected_edges(net, node_id):
    """Return all edge IDs (incoming + outgoing) connected to a junction."""
    node = net.getNode(node_id)
    incoming = node.getIncoming()
    outgoing = node.getOutgoing()
    return {e.getID() for e in incoming + outgoing}


def apply_speed_reduction(net_file, node_id, output_file, reduction_factor=0.8):
    """Speed breaker simulation: reduce speed limit only on INCOMING (approach) edges to this junction."""
    net = sumolib.net.readNet(net_file)
    node = net.getNode(node_id)
    connected_edge_ids = {e.getID() for e in node.getIncoming()}  # incoming only, not outgoing

    tree = ET.parse(net_file)
    root = tree.getroot()
    changed = 0

    for edge_elem in root.findall("edge"):
        if edge_elem.get("id") in connected_edge_ids:
            for lane_elem in edge_elem.findall("lane"):
                current_speed = float(lane_elem.get("speed"))
                lane_elem.set("speed", str(round(current_speed * reduction_factor, 2)))
                changed += 1

    tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"  Applied speed reduction to {changed} lanes across {len(connected_edge_ids)} edges.")
    return output_file


def apply_signal_retiming(net_file, node_id, output_file, green_multiplier=1.3):
    """
    Signal retiming simulation: extend green phase duration at this
    junction's traffic light by green_multiplier.

    BUGFIX: this function previously ended right after reading the network
    (`net = sumolib.net.readNet(net_file)`), with no further logic and no
    return statement -- so it silently did nothing and returned None. The
    actual retiming logic below existed in the file but was orphaned after
    a different function's `return`, so it never ran. That meant every
    "signal_retiming" scenario actually simulated the UNMODIFIED network
    (or crashed downstream on a missing output file), which is why
    intervention results looked random/harmful instead of showing a real
    effect.
    """
    net = sumolib.net.readNet(net_file)

    # Find the tlLogic ID that actually controls this node
    tls_id_for_node = None
    for tls in net.getTrafficLights():
        controlled_nodes = {conn[0].getEdge().getToNode().getID() for conn in tls.getConnections()}
        if node_id in controlled_nodes or tls.getID() == node_id:
            tls_id_for_node = tls.getID()
            break

    if tls_id_for_node is None:
        print(f"  WARNING: No traffic light found controlling node {node_id}. Copying network unchanged.")
        import shutil
        shutil.copy(net_file, output_file)
        return output_file

    tree = ET.parse(net_file)
    root = tree.getroot()
    changed = 0

    for tl_elem in root.findall("tlLogic"):
        if tl_elem.get("id") == tls_id_for_node:
            for phase in tl_elem.findall("phase"):
                state = phase.get("state")
                if "G" in state or "g" in state:
                    dur = float(phase.get("duration"))
                    phase.set("duration", str(round(dur * green_multiplier, 1)))
                    changed += 1

    tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"  Applied signal retiming to tlLogic '{tls_id_for_node}', {changed} green phases extended.")
    return output_file


def apply_add_signal(net_file, node_id, output_file):
    """
    Converts an unsignalized junction into a signal-controlled one using
    netconvert's built-in TLS conversion.

    NOTE: Two attempts were made to "improve" this (fixed-duration retuning,
    then switching actuated->static) -- both made add_signal's conflict
    increase WORSE, not better (+8% -> +16.5% -> +25.2% mean across test
    junctions), disproving the theories behind those changes. Reverted back
    to this original simple version, which produced the mildest (though
    still net-positive) conflict increase. That +8% average increase should
    be reported as a genuine finding, not treated as a bug: a newly-added
    signal at a previously free-flowing junction plausibly causes real
    stop-and-go conflicts during a short simulation window, and further
    "fixing" this without deeper SUMO-specific investigation (more sim time,
    proper detector placement, real signal warrant analysis) risks doing
    more harm than good. Do not modify this function again without first
    verifying a specific, evidenced hypothesis against the actual SUMO
    output -- not a plausible-sounding guess.
    """
    cmd = [
        "netconvert",
        "--sumo-net-file", net_file,
        "--tls.set", node_id,
        "--tls.default-type", "actuated",
        "-o", output_file,
        "--no-warnings", "true"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        print(f"  ERROR adding signal: {result.stderr[-500:]}")
        return None
    print(f"  Converted junction '{node_id}' to a signal-controlled junction.")
    return output_file


def run_scenario(net_file, sumocfg, node_id, intervention_type, scenario_tag):
    """Apply intervention (if any), run simulation, return path to conflict output."""
    if intervention_type == "speed_breaker":
        modified_net = f"temp_net_{scenario_tag}.net.xml"
        apply_speed_reduction(net_file, node_id, modified_net)
    elif intervention_type == "signal_retiming":
        modified_net = f"temp_net_{scenario_tag}.net.xml"
        apply_signal_retiming(net_file, node_id, modified_net)
    elif intervention_type == "none":
        modified_net = net_file
    else:
        raise ValueError(f"Unknown intervention type: {intervention_type}")

    ssm_output = f"ssm_{scenario_tag}.xml"

    cmd = [
        "sumo", "-c", sumocfg,
        "--net-file", modified_net,
        "--device.ssm.probability", "1.0",
        "--device.ssm.file", ssm_output,
        "--device.ssm.measures", "TTC PET DRAC",
        "--device.ssm.thresholds", "3.0 2.0 3.0",
        "--device.ssm.geo", "true",
        "--no-warnings", "true",
        "--time-to-teleport", "90",
        "--max-num-vehicles", "2000"
    ]

    print(f"  Running SUMO for scenario '{scenario_tag}'...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)  # 15 min hard cap
    except subprocess.TimeoutExpired:
        print("  TIMEOUT: scenario exceeded 15 minutes, something is likely gridlocked.")
        return None

    if result.returncode != 0:
        print(f"  ERROR running scenario (return code {result.returncode}):")
        print(f"  STDOUT (last 1000 chars): {result.stdout[-1000:]}")
        print(f"  STDERR (last 1000 chars): {result.stderr[-1000:]}")
        return None

    return ssm_output


def apply_turn_restriction(net_file, node_id, output_file, banned_dir="l"):
    """Removes connections matching a turn direction by decompiling the network to plain XML,
    editing connections there, and recompiling — avoids crashes from editing compiled net.xml directly."""
    prefix = output_file.replace(".net.xml", "") + "_plain"

    decompile_cmd = ["netconvert", "--sumo-net-file", net_file, "--plain-output-prefix", prefix, "--no-warnings", "true"]
    r1 = subprocess.run(decompile_cmd, capture_output=True, text=True, timeout=60)
    if r1.returncode != 0:
        print(f"  ERROR decompiling network: {r1.stderr[-400:]}")
        return None

    con_file = prefix + ".con.xml"
    net = sumolib.net.readNet(net_file)
    node = net.getNode(node_id)
    connected_edge_ids = {e.getID() for e in node.getIncoming()}

    tree = ET.parse(con_file)
    root = tree.getroot()
    removed = 0
    for conn in list(root.findall("connection")):
        if conn.get("from") in connected_edge_ids and conn.get("dir") == banned_dir:
            root.remove(conn)
            removed += 1
    tree.write(con_file, encoding="UTF-8", xml_declaration=True)

    recompile_cmd = [
        "netconvert",
        "--node-files", prefix + ".nod.xml",
        "--edge-files", prefix + ".edg.xml",
        "--connection-files", con_file,
        "--tllogic-files", prefix + ".tll.xml",
        "--type-files", prefix + ".typ.xml",
        "-o", output_file,
        "--no-warnings", "true"
    ]
    r2 = subprocess.run(recompile_cmd, capture_output=True, text=True, timeout=60)
    if r2.returncode != 0:
        print(f"  ERROR recompiling network: {r2.stderr[-400:]}")
        return None

    print(f"  Removed {removed} '{banned_dir}' connections at junction {node_id} (safely recompiled).")
    return output_file