import sumolib

net = sumolib.net.readNet("central_kolkata.net.xml")
node_id = "cluster_10281958925_10281958926_6508834064_6508834065_#1more"  # adjust if your actual full ID differs

node = net.getNode(node_id)
print(f"Node type: {node.getType()}")

print("\nAll traffic lights in network and their IDs:")
all_tls_ids = [tls.getID() for tls in net.getTrafficLights()]
print(f"Total traffic lights found: {len(all_tls_ids)}")

matching = [t for t in all_tls_ids if node_id in t or t in node_id]
print(f"\nTLS IDs that partially match this node_id: {matching}")

print("\nChecking connections for each TLS to see which nodes they actually control:")
for tls in net.getTrafficLights():
    controlled_nodes = set()
    for conn in tls.getConnections():
        controlled_nodes.add(conn[0].getEdge().getToNode().getID())
    if node_id in controlled_nodes:
        print(f"  MATCH: tls '{tls.getID()}' controls node '{node_id}'")