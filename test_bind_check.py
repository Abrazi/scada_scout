"""Test if server can bind to specific addresses"""
import socket
import sys

def test_bind(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(1)
        actual_host, actual_port = sock.getsockname()
        print(f"✅ Successfully bound to {actual_host}:{actual_port}")
        sock.close()
        return True
    except Exception as e:
        print(f"❌ Failed to bind to {host}:{port} - {e}")
        return False

print("Testing network binding capabilities:\n")
print("1. Localhost (127.0.0.1):")
test_bind("127.0.0.1", 10102)

print("\n2. All interfaces (0.0.0.0):")
test_bind("0.0.0.0", 10102)

print("\n3. Getting actual network interfaces:")
try:
    import netifaces
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                ip = addr['addr']
                print(f"   Interface {iface}: {ip}")
except ImportError:
    print("   (netifaces not installed, install with: pip install netifaces)")
    import subprocess
    result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
    if result.returncode == 0:
        lines = [l.strip() for l in result.stdout.split('\n') if 'inet ' in l and not 'inet6' in l]
        for line in lines:
            print(f"   {line}")
