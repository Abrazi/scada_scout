#!/usr/bin/env python3
"""Debug script to see what signals are being parsed from test.icd"""

from src.core.scd_parser import SCDParser

scd_path = "/home/majid/Documents/scada_scout/test.icd"
ied_name = "GPS01GPC01UPM01FCB01"

parser = SCDParser(scd_path)
root = parser.get_structure(ied_name)

def iter_signals(node, depth=0):
    indent = "  " * depth
    print(f"{indent}Node: {node.name} ({len(node.signals)} signals, {len(node.children)} children)")
    
    # Show first few signals from this node
    for i, sig in enumerate(node.signals[:3]):
        print(f"{indent}  Signal: {sig.address}")
        if sig.description:
            print(f"{indent}    Desc: {sig.description[:100]}")
        if i >= 2:
            if len(node.signals) > 3:
                print(f"{indent}  ... and {len(node.signals) - 3} more signals")
            break
    
    for child in node.children:
        iter_signals(child, depth + 1)

print(f"\n=== Structure for {ied_name} ===")
print(f"Root: {root.name}")
print(f"Total children: {len(root.children)}")
print()

iter_signals(root)

# Count total signals
total_signals = 0
def count_signals(node):
    global total_signals
    total_signals += len(node.signals)
    for child in node.children:
        count_signals(child)

count_signals(root)
print(f"\n=== Total signals: {total_signals} ===")

# Show some example signal addresses
print("\n=== Sample signal addresses ===")
def collect_some_signals(node, limit=10):
    result = []
    for sig in node.signals:
        result.append(sig)
        if len(result) >= limit:
            return result
    for child in node.children:
        result.extend(collect_some_signals(child, limit - len(result)))
        if len(result) >= limit:
            return result
    return result

samples = collect_some_signals(root, 10)
for sig in samples:
    print(f"  {sig.address}")
    if sig.fc:
        print(f"    FC: {sig.fc}")
    if sig.description:
        print(f"    Desc: {sig.description[:80]}")
