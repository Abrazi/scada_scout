#!/usr/bin/env python3
"""Quick check if IEC 61850 server is running"""
import socket
import sys

def check_port(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            return True, "Port is OPEN (server listening)"
        else:
            return False, f"Port is CLOSED (error code {result})"
    except Exception as e:
        return False, f"Error: {e}"

ports_to_check = [102, 10002, 10102]
hosts = ["127.0.0.1", "0.0.0.0"]

print("Checking for IEC 61850 servers...\n")

for port in ports_to_check:
    print(f"Port {port}:")
    for host in ["127.0.0.1"]:
        is_open, msg = check_port(host, port)
        symbol = "✅" if is_open else "❌"
        print(f"  {symbol} {host}:{port} - {msg}")
    print()

# Check with lsof
print("\nProcesses listening on these ports:")
import subprocess
try:
    result = subprocess.run(['lsof', '-i', '-P', '-n'], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if any(f':{p}' in line for p in ports_to_check):
            print(f"  {line}")
    if not any(f':{p}' in line for p in ports_to_check for line in result.stdout.split('\n')):
        print("  (none found)")
except Exception as e:
    print(f"  Could not run lsof: {e}")
