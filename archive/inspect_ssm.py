import xml.etree.ElementTree as ET

tree = ET.parse("central_kolkata_ssm.xml")
root = tree.getroot()

conflicts = root.findall("conflict")
print(f"Total <conflict> elements found: {len(conflicts)}")

if conflicts:
    first = conflicts[0]
    print("\n--- Attributes on first <conflict> element ---")
    for key, value in first.attrib.items():
        print(f"  {key} = {value}")

    print("\n--- Child elements on first <conflict> ---")
    for child in first:
        print(f"  <{child.tag}> attrib={child.attrib}")
else:
    print("No <conflict> tags found at all. Checking root structure instead...")
    print(f"Root tag: {root.tag}")
    print("Direct children of root:")
    for child in root:
        print(f"  <{child.tag}> attrib={child.attrib}")