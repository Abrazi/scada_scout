from PySide6.QtCore import QObject, Signal, QSettings
from datetime import datetime
import binascii
import socket
import psutil
import json
import os
import threading
import shutil
import subprocess
import tempfile
import time
import signal


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

        # dumpcap / FIFO fallback
        self._dumpcap_path = shutil.which('dumpcap')
        self._dumpcap_proc = None
        self._fifo_path = None
        self._dumpcap_thread = None
        self._stop_event = threading.Event()

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

        # Read preferred capture backend from settings (Auto/AsyncSniffer/dumpcap)
        try:
            qs = QSettings("ScadaScout", "UI")
            raw = qs.value("capture_backend", "Auto")
            if isinstance(raw, str):
                if "Async" in raw:
                    self._preferred_backend = 'async'
                elif "dumpcap" in raw:
                    self._preferred_backend = 'dumpcap'
                else:
                    self._preferred_backend = 'auto'
            else:
                self._preferred_backend = 'auto'
        except Exception:
            self._preferred_backend = 'auto'

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

        # Decide backend based on preference and availability
        try:
            from sys import platform
            is_posix = platform.startswith('linux') or platform.startswith('darwin') or platform.startswith('freebsd')
        except Exception:
            is_posix = False

        # Helper to try AsyncSniffer
        def try_async():
            try:
                kwargs = {'prn': self._packet_callback, 'filter': filter_str, 'store': False}
                if self._iface:
                    kwargs['iface'] = self._iface
                try:
                    self.packet_captured.emit(f"DEBUG: starting AsyncSniffer kwargs={kwargs}")
                except Exception:
                    pass
                self._sniffer = self._AsyncSniffer(**kwargs)
                self._sniffer.start()
                return True, None
            except Exception as e:
                self._sniffer = None
                return False, e

        # Helper to try dumpcap fallback
        def try_dumpcap():
            if not is_posix:
                return False, RuntimeError("dumpcap fallback is only supported on POSIX platforms")
            if not self._dumpcap_path:
                return False, RuntimeError("dumpcap not found on PATH")
            try:
                started = self._start_dumpcap_fifo(filter_str, iface)
                return started, None
            except Exception as e:
                return False, e

        # Branch based on preference
        if self._preferred_backend == 'async':
            ok, err = try_async()
            if not ok:
                self.error_occurred.emit(f"AsyncSniffer failed: {err}")
            return

        if self._preferred_backend == 'dumpcap':
            ok, err = try_dumpcap()
            if not ok:
                # emit helpful guidance
                self._emit_dumpcap_guidance(err)
                self.error_occurred.emit(f"Dumpcap fallback failed: {err}")
            return

        # Auto mode: prefer AsyncSniffer, fallback to dumpcap on POSIX
        ok, err = try_async()
        if ok:
            return
        # Async failed; try dumpcap if available
        if is_posix:
            ok2, err2 = try_dumpcap()
            if ok2:
                try:
                    self.packet_captured.emit(f"DEBUG: using dumpcap fallback at {self._fifo_path}")
                except Exception:
                    pass
                return
            else:
                # Provide guidance if dumpcap not usable
                self._emit_dumpcap_guidance(err2)

        # final fallback: emit AsyncSniffer error
        self.error_occurred.emit(f"Failed to start sniffer: {err}")

    def stop_capture(self):
        """Stop capturing packets if running."""
        if not self._scapy_available:
            return

        try:
            # Stop AsyncSniffer if running
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

            # Stop dumpcap fallback if active
            if self._dumpcap_proc is not None:
                try:
                    # signal termination
                    self._stop_event.set()
                    try:
                        self._dumpcap_proc.terminate()
                    except Exception:
                        pass
                    # wait briefly
                    self._dumpcap_proc.wait(timeout=2)
                except Exception:
                    pass
                finally:
                    self._dumpcap_proc = None

            if self._dumpcap_thread is not None:
                try:
                    self._dumpcap_thread.join(timeout=2)
                except Exception:
                    pass
                finally:
                    self._dumpcap_thread = None

            # remove FIFO if exists
            if self._fifo_path and os.path.exists(self._fifo_path):
                try:
                    os.unlink(self._fifo_path)
                except Exception:
                    pass
                finally:
                    self._fifo_path = None
        except Exception as e:
            self.error_occurred.emit(f"Failed to stop sniffer: {e}")

    # --- dumpcap FIFO helpers ---
    def _start_dumpcap_fifo(self, filter_str: str = "", iface: str = None) -> bool:
        """Create FIFO and spawn dumpcap writing pcap to it; start reader thread.
        Returns True on success.
        """
        # create fifo
        try:
            fd, fifo = tempfile.mkstemp(prefix='scadascout_fifo_', dir=tempfile.gettempdir())
            os.close(fd)
            os.unlink(fifo)
            os.mkfifo(fifo, 0o600)
            self._fifo_path = fifo
        except Exception as e:
            raise RuntimeError(f"Failed to create FIFO: {e}")

        # build dumpcap command
        cmd = [self._dumpcap_path, '-w', self._fifo_path]
        if iface:
            cmd = [self._dumpcap_path, '-i', iface, '-w', self._fifo_path]
        if filter_str:
            cmd.extend(['-f', filter_str])

        # spawn dumpcap
        try:
            self._stop_event.clear()
            # Start dumpcap detached; ensure stdout/stderr captured for errors
            self._dumpcap_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
        except Exception as e:
            # cleanup fifo
            try:
                if self._fifo_path and os.path.exists(self._fifo_path):
                    os.unlink(self._fifo_path)
            except Exception:
                pass
            self._fifo_path = None
            raise RuntimeError(f"Failed to start dumpcap: {e}")

        # start reader thread
        self._dumpcap_thread = threading.Thread(target=self._read_fifo_loop, daemon=True)
        self._dumpcap_thread.start()
        return True

    def _read_fifo_loop(self):
        """Continuously read pcap packets from FIFO using Scapy RawPcapReader and dispatch.
        This runs in a separate thread.
        """
        try:
            # wait until fifo writer opens
            while not os.path.exists(self._fifo_path) and not self._stop_event.is_set():
                time.sleep(0.05)

            from scapy.utils import RawPcapReader
            while not self._stop_event.is_set():
                try:
                    reader = RawPcapReader(self._fifo_path)
                except Exception as e:
                    # Possibly fifo not yet writable; wait and retry
                    time.sleep(0.1)
                    continue

                try:
                    for pkt_data, pkt_meta in reader:
                        if self._stop_event.is_set():
                            break
                        try:
                            # build scapy packet from raw bytes
                            from scapy.all import Ether
                            pkt = Ether(pkt_data)
                            # dispatch to processing
                            try:
                                self._packet_callback(pkt)
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
                finally:
                    try:
                        reader.close()
                    except Exception:
                        pass

                # small sleep to avoid tight loop on EOF
                time.sleep(0.05)
        except Exception as e:
            try:
                self.error_occurred.emit(f"Dumpcap reader error: {e}")
            except Exception:
                pass
        finally:
            # ensure dumpcap process terminated
            try:
                if self._dumpcap_proc is not None:
                    try:
                        self._dumpcap_proc.terminate()
                    except Exception:
                        pass
            except Exception:
                pass

    def _emit_dumpcap_guidance(self, error):
        """Emit user-friendly guidance for installing/configuring dumpcap when fallback fails."""
        try:
            from sys import platform
            is_linux = platform.startswith('linux')
            is_mac = platform.startswith('darwin')
        except Exception:
            is_linux = is_mac = False

        if not self._dumpcap_path:
            if is_linux:
                msg = (
                    "`dumpcap` not found. Install Wireshark/dumpcap.\n"
                    "On Debian/Ubuntu: sudo apt install wireshark\n"
                    "On Fedora: sudo dnf install wireshark-cli\n"
                    "After install, give dumpcap capture capability:\n"
                    "  sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/bin/dumpcap\n"
                )
            elif is_mac:
                msg = (
                    "`dumpcap` not found. Install Wireshark for macOS and allow packet capture permissions."
                )
            else:
                msg = "`dumpcap` not available on this platform."
            try:
                self.error_occurred.emit(msg)
            except Exception:
                pass
            return

        # dumpcap present but failed to start
        # Suggest setcap for dumpcap binary
        try:
            setcap_cmd = f"sudo setcap 'cap_net_raw,cap_net_admin+eip' {self._dumpcap_path}"
        except Exception:
            setcap_cmd = "sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/bin/dumpcap"

        guidance = (
            f"Failed to use dumpcap ({error}).\n"
            "If you want to use dumpcap without sudo, grant it capture capabilities (one-time):\n"
            f"  {setcap_cmd}\n\n"
            "Alternatively run the application as root (not recommended) or install a capture driver/tool appropriate for your OS."
        )
        try:
            self.error_occurred.emit(guidance)
        except Exception:
            pass

