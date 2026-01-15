from PySide6.QtCore import QObject, Signal
from datetime import datetime
import binascii
import socket
import psutil
import json
import os
import threading


class PacketCaptureWorker(QObject):
    """Background packet capture helper using scapy.

    Features:
    - Uses scapy AsyncSniffer when available to capture in background
    - Emits detailed packet text via `packet_captured` signal
    - Optional file logging (plain text or JSON)
    - Interface selection or local IP override for TX/RX detection
    """
    packet_captured = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sniffer = None
        self._AsyncSniffer = None
        self._scapy_available = False
        self._scapy_error = None

        # Logging options
        self._log_file = None
        self._log_json = False
        self._log_lock = threading.Lock()
        # Rotation options
        self._max_log_size = 10 * 1024 * 1024  # 10 MB default
        self._max_log_files = 5

        # Interface/local IP detection
        self._iface = None
        self._local_ips = set()

        try:
            from scapy.all import AsyncSniffer
            self._AsyncSniffer = AsyncSniffer
            self._scapy_available = True
        except Exception as e:
            self._scapy_available = False
            self._scapy_error = str(e)

        # Populate local IPs by default
        self._gather_local_ips()

    def _gather_local_ips(self, iface: str = None):
        """Populate `self._local_ips` either for given interface or all interfaces."""
        self._local_ips.clear()
        try:
            addrs = psutil.net_if_addrs()
            if iface and iface in addrs:
                candidates = addrs.get(iface, [])
            else:
                # flatten all interfaces
                candidates = [a for vals in addrs.values() for a in vals]

            for a in candidates:
                if getattr(a, 'family', None) == socket.AF_INET:
                    self._local_ips.add(a.address)
        except Exception:
            try:
                hostname = socket.gethostname()
                self._local_ips.add(socket.gethostbyname(hostname))
            except Exception:
                pass

    def set_log_file(self, path: str, json_format: bool = False):
        """Enable logging to `path`. Pass `None` to disable."""
        self._log_file = path
        self._log_json = bool(json_format)
        # Try to create the file and write a header so the file exists immediately
        if self._log_file:
            try:
                dirname = os.path.dirname(self._log_file)
                if dirname and not os.path.exists(dirname):
                    os.makedirs(dirname, exist_ok=True)
                header = f"# Packet log created at {datetime.now().isoformat()}\n"
                with open(self._log_file, 'a', encoding='utf-8') as f:
                    f.write(header)
            except Exception as e:
                try:
                    self.error_occurred.emit(f"Failed to create log file: {e}")
                except Exception:
                    pass

    def set_interface(self, iface: str):
        """Select a network interface name for capture and local IP detection."""
        self._iface = iface
        self._gather_local_ips(iface=iface)

    def set_log_rotation(self, max_bytes: int, max_files: int = 5):
        """Configure log rotation: rotate when file reaches `max_bytes`, keep `max_files` rotated files."""
        try:
            self._max_log_size = int(max_bytes) if max_bytes else 0
            self._max_log_files = max(1, int(max_files))
        except Exception:
            # ignore invalid inputs
            pass

    def override_local_ips(self, ips):
        """Manually override local IP list. `ips` can be a string or iterable."""
        self._local_ips.clear()
        if not ips:
            return
        if isinstance(ips, str):
            self._local_ips.add(ips)
            return
        for ip in ips:
            self._local_ips.add(ip)

    def _emit_and_maybe_log(self, text: str, pkt=None):
        # Emit to UI
        try:
            self.packet_captured.emit(text)
        except Exception:
            pass

        # Optionally append to file
        if self._log_file:
            try:
                # Ensure rotation if needed
                try:
                    if self._max_log_size and os.path.exists(self._log_file):
                        if os.path.getsize(self._log_file) >= self._max_log_size:
                            # rotate files: logfile -> logfile.1, logfile.1 -> logfile.2, ...
                            for i in range(self._max_log_files - 1, 0, -1):
                                src = f"{self._log_file}.{i}"
                                dst = f"{self._log_file}.{i+1}"
                                if os.path.exists(src):
                                    try:
                                        os.replace(src, dst)
                                    except Exception:
                                        pass
                            # move current to .1
                            try:
                                os.replace(self._log_file, f"{self._log_file}.1")
                            except Exception:
                                pass
                except Exception:
                    pass
                with self._log_lock:
                    mode = 'a'
                    with open(self._log_file, mode, encoding='utf-8') as f:
                        if self._log_json and pkt is not None:
                            # Build structured JSON
                            try:
                                from scapy.all import IP, TCP, Raw
                                data = {}
                                ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                                data['time'] = ts
                                if IP in pkt:
                                    ip = pkt[IP]
                                    data['src'] = getattr(ip, 'src', None)
                                    data['dst'] = getattr(ip, 'dst', None)
                                if TCP in pkt:
                                    tcp = pkt[TCP]
                                    data['sport'] = getattr(tcp, 'sport', None)
                                    data['dport'] = getattr(tcp, 'dport', None)
                                    data['seq'] = getattr(tcp, 'seq', None)
                                    data['ack'] = getattr(tcp, 'ack', None)
                                    data['flags'] = str(getattr(tcp, 'flags', None))
                                if Raw in pkt:
                                    payload = pkt[Raw].load
                                    try:
                                        data['payload_hex'] = binascii.hexlify(payload).decode()
                                    except Exception:
                                        data['payload_hex'] = None
                                data['raw'] = text
                                f.write(json.dumps(data, ensure_ascii=False) + '\n')
                            except Exception:
                                # Fallback: write raw text
                                f.write(text + '\n')
                        else:
                            f.write(text + '\n')
            except Exception as e:
                try:
                    self.error_occurred.emit(f"Failed to write packet log: {e}")
                except Exception:
                    pass

    def _packet_callback(self, pkt):
        try:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            from scapy.all import Ether, IP, TCP, Raw

            direction = 'UNK'
            details = []
            if IP in pkt:
                ip = pkt[IP]
                src = getattr(ip, 'src', '?')
                dst = getattr(ip, 'dst', '?')
                # Determine direction based on local IPs
                if src in self._local_ips:
                    direction = 'TX'
                elif dst in self._local_ips:
                    direction = 'RX'

                ethtxt = ''
                try:
                    eth = pkt[Ether]
                    ethtxt = f"  ETH  {eth.src} → {eth.dst}\n"
                except Exception:
                    pass

                iptxt = f"  IP   {src} → {dst}  TTL={getattr(ip,'ttl', '?')}\n"

                if TCP in pkt:
                    tcp = pkt[TCP]
                    tcptxt = (
                        f"  TCP  {getattr(tcp,'sport','?')} → {getattr(tcp,'dport','?')}\n"
                        f"       SEQ={getattr(tcp,'seq','?')} ACK={getattr(tcp,'ack','?')} WIN={getattr(tcp,'window','?')}\n"
                        f"       FLAGS={getattr(tcp,'flags','?')}\n"
                    )
                else:
                    tcptxt = ''

                payload_txt = ''
                if Raw in pkt:
                    payload = pkt[Raw].load
                    try:
                        payload_hex = binascii.hexlify(payload).decode()
                    except Exception:
                        payload_hex = str(payload)
                    try:
                        payload_ascii = payload.decode(errors='replace')
                    except Exception:
                        payload_ascii = str(payload)
                    payload_txt = f"  PAYLOAD ({len(payload)} bytes)\n  HEX : {payload_hex}\n  ASCII: {payload_ascii}\n"
                else:
                    payload_txt = "  PAYLOAD: <none>\n"

                # Add header
                details.append(f"[{ts}] [{direction}] PACKET\n")
                if ethtxt:
                    details.append(ethtxt)
                details.append(iptxt)
                if tcptxt:
                    details.append(tcptxt)
                details.append(payload_txt)

                # Full scapy dump (no color)
                try:
                    scapy_dump = pkt.show(dump=True)
                    details.append("\n-- Scapy dump --\n")
                    details.append(scapy_dump)
                except Exception:
                    pass

                full = "".join(details)
            else:
                full = f"[{ts}] [UNK] PACKET\n" + pkt.show(dump=True)

            # Emit and optionally log
            self._emit_and_maybe_log(full, pkt=pkt)
        except Exception as e:
            try:
                self.error_occurred.emit(f"Packet processing error: {e}")
            except Exception:
                pass

    def start_capture(self, filter_str: str = "", iface: str = None):
        """Start capturing packets.

        filter_str is a BPF-style filter (e.g., "tcp port 102"). Empty string means no filter.
        `iface` optionally selects the network interface name for AsyncSniffer.
        """
        if not self._scapy_available:
            self.error_occurred.emit(f"Scapy not available: {self._scapy_error}")
            return

        if self._sniffer is not None:
            # already running
            return

        if iface:
            self._iface = iface
            # refresh local ip list for chosen iface
            self._gather_local_ips(iface=iface)

        try:
            # AsyncSniffer runs sniff() in a background thread and exposes start/stop.
            # Note: On Windows you must have Npcap/WinPcap installed and run as Administrator.
            kwargs = {'prn': self._packet_callback, 'filter': filter_str, 'store': False}
            if self._iface:
                kwargs['iface'] = self._iface
            # Emit a short debug message to help diagnose why capture may not start
            try:
                self.packet_captured.emit(f"DEBUG: starting AsyncSniffer kwargs={kwargs}")
            except Exception:
                pass
            self._sniffer = self._AsyncSniffer(**kwargs)
            self._sniffer.start()
        except Exception as e:
            self._sniffer = None
            self.error_occurred.emit(f"Failed to start sniffer: {e}")

    def stop_capture(self):
        """Stop capturing packets if running."""
        if not self._scapy_available:
            return

        try:
            if self._sniffer is not None:
                try:
                    self._sniffer.stop()
                except Exception:
                    try:
                        self._sniffer.running = False
                    except Exception:
                        pass
                finally:
                    self._sniffer = None
        except Exception as e:
            self.error_occurred.emit(f"Failed to stop sniffer: {e}")

