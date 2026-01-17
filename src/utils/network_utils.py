"""
Cross-platform network utilities
Provides consistent network operations across Windows, Linux, and macOS
"""
import socket
import struct
import platform
import logging
from typing import Tuple, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NetworkInterface:
    """Represents a network interface"""
    name: str
    ip_address: str
    netmask: str
    mac_address: str = ""
    is_up: bool = True


class NetworkUtils:
    """Cross-platform network utilities"""
    
    @staticmethod
    def check_tcp_port(host: str, port: int, timeout: float = 2.0) -> bool:
        """
        Check if TCP port is reachable (cross-platform)
        
        Args:
            host: IP address or hostname
            port: Port number
            timeout: Connection timeout in seconds
            
        Returns:
            True if port is open and reachable
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"Port check failed for {host}:{port} - {e}")
            return False
    
    @staticmethod
    def check_host_reachable(host: str, timeout: float = 2.0) -> bool:
        """
        Check if host is reachable using socket method (cross-platform)
        More reliable than ping and doesn't require admin privileges
        
        Args:
            host: IP address or hostname
            timeout: Timeout in seconds
            
        Returns:
            True if host responds
        """
        # Try common ports that are likely to be filtered but respond to connection attempts
        # We're not looking for successful connection, just network reachability
        common_ports = [80, 443, 22, 23, 102, 502, 2404]  # HTTP, HTTPS, SSH, Telnet, IEC61850, Modbus, IEC104
        
        for port in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout / len(common_ports))
                # Even if connection is refused, host is reachable
                sock.connect_ex((host, port))
                sock.close()
                return True  # Host responded (even with refusal)
            except socket.timeout:
                continue
            except Exception:
                continue
        
        # Fallback: Try to resolve hostname
        try:
            socket.gethostbyname(host)
            return True
        except:
            return False
    
    @staticmethod
    def get_local_ip() -> str:
        """
        Get primary local IP address (cross-platform)
        
        Returns:
            Local IP address as string
        """
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1)
            # Doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return '127.0.0.1'
    
    @staticmethod
    def get_network_interfaces() -> List[NetworkInterface]:
        """
        Get list of network interfaces (cross-platform)
        
        Returns:
            List of NetworkInterface objects
        """
        interfaces = []
        
        try:
            # Try using psutil (cross-platform)
            import psutil
            
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            
            for interface_name, addr_list in addrs.items():
                for addr in addr_list:
                    if addr.family == socket.AF_INET:  # IPv4
                        is_up = stats[interface_name].isup if interface_name in stats else True
                        
                        # Get MAC address
                        mac = ""
                        for a in addr_list:
                            if a.family == psutil.AF_LINK:
                                mac = a.address
                                break
                        
                        interfaces.append(NetworkInterface(
                            name=interface_name,
                            ip_address=addr.address,
                            netmask=addr.netmask or "255.255.255.0",
                            mac_address=mac,
                            is_up=is_up
                        ))
            
            return interfaces
            
        except ImportError:
            logger.warning("psutil not available, using basic interface detection")
            
            # Fallback: Basic method
            try:
                local_ip = NetworkUtils.get_local_ip()
                interfaces.append(NetworkInterface(
                    name="default",
                    ip_address=local_ip,
                    netmask="255.255.255.0"
                ))
            except:
                pass
            
            return interfaces
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """
        Validate IP address format
        
        Args:
            ip: IP address string
            
        Returns:
            True if valid IPv4 address
        """
        try:
            socket.inet_aton(ip)
            parts = ip.split('.')
            return len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts)
        except:
            return False
    
    @staticmethod
    def validate_port(port: int) -> bool:
        """
        Validate port number
        
        Args:
            port: Port number
            
        Returns:
            True if valid port (1-65535)
        """
        return 1 <= port <= 65535
    
    @staticmethod
    def get_hostname() -> str:
        """
        Get system hostname (cross-platform)
        
        Returns:
            Hostname as string
        """
        try:
            return socket.gethostname()
        except:
            return "unknown"
    
    @staticmethod
    def resolve_hostname(hostname: str) -> Optional[str]:
        """
        Resolve hostname to IP address
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            IP address or None if resolution fails
        """
        try:
            return socket.gethostbyname(hostname)
        except:
            return None
    
    @staticmethod
    def get_platform_info() -> dict:
        """
        Get platform-specific network information
        
        Returns:
            Dictionary with platform details
        """
        return {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'hostname': NetworkUtils.get_hostname(),
            'local_ip': NetworkUtils.get_local_ip()
        }


class NetworkScriptGenerator:
    """Generate network configuration scripts for different platforms"""
    
    @staticmethod
    def generate_windows_batch(ip_addresses: List[str], adapter_name: str = "Ethernet") -> str:
        """
        Generate Windows batch script to configure IP addresses
        
        Args:
            ip_addresses: List of IP addresses to configure
            adapter_name: Network adapter name
            
        Returns:
            Batch script content
        """
        script = "@echo off\n"
        script += "REM SCADA Scout - Network Configuration Script\n"
        script += "REM Generated for Windows\n"
        script += "REM Run as Administrator\n\n"
        
        script += "echo ========================================\n"
        script += "echo SCADA Scout Network Configuration\n"
        script += "echo ========================================\n"
        script += "echo.\n\n"
        
        script += "REM Check for admin privileges\n"
        script += "net session >nul 2>&1\n"
        script += "if %errorLevel% neq 0 (\n"
        script += "    echo ERROR: This script requires Administrator privileges\n"
        script += "    echo Please right-click and select 'Run as Administrator'\n"
        script += "    pause\n"
        script += "    exit /b 1\n"
        script += ")\n\n"
        
        script += f"echo Configuring {len(ip_addresses)} IP address(es) on adapter: {adapter_name}\n"
        script += "echo.\n\n"
        
        for i, ip in enumerate(ip_addresses):
            if ip in ["127.0.0.1", "0.0.0.0"] or not NetworkUtils.validate_ip_address(ip):
                continue
            
            # Use /24 subnet by default
            script += f"echo [{i+1}/{len(ip_addresses)}] Adding IP: {ip}\n"
            script += f'netsh interface ip add address "{adapter_name}" {ip} 255.255.255.0\n'
            script += "if %errorLevel% neq 0 (\n"
            script += f"    echo WARNING: Failed to add {ip}\n"
            script += ") else (\n"
            script += f"    echo SUCCESS: Added {ip}\n"
            script += ")\n"
            script += "echo.\n\n"
        
        script += "echo ========================================\n"
        script += "echo Configuration complete!\n"
        script += "echo ========================================\n"
        script += "pause\n"
        
        return script
    
    @staticmethod
    def generate_linux_shell(ip_addresses: List[str], interface_name: str = "eth0") -> str:
        """
        Generate Linux shell script to configure IP addresses
        
        Args:
            ip_addresses: List of IP addresses to configure
            interface_name: Network interface name
            
        Returns:
            Shell script content
        """
        script = "#!/bin/bash\n"
        script += "# SCADA Scout - Network Configuration Script\n"
        script += "# Generated for Linux\n"
        script += "# Run with: sudo bash this_script.sh\n\n"
        
        script += "echo '========================================'\n"
        script += "echo 'SCADA Scout Network Configuration'\n"
        script += "echo '========================================'\n"
        script += "echo ''\n\n"
        
        script += "# Check for root privileges\n"
        script += "if [ \"$EUID\" -ne 0 ]; then\n"
        script += "    echo 'ERROR: This script must be run as root'\n"
        script += "    echo 'Please run: sudo bash $0'\n"
        script += "    exit 1\n"
        script += "fi\n\n"
        
        script += f"echo 'Configuring {len(ip_addresses)} IP address(es) on interface: {interface_name}'\n"
        script += "echo ''\n\n"
        
        for i, ip in enumerate(ip_addresses):
            if ip in ["127.0.0.1", "0.0.0.0"] or not NetworkUtils.validate_ip_address(ip):
                continue
            
            script += f"echo '[{i+1}/{len(ip_addresses)}] Adding IP: {ip}'\n"
            script += f"ip addr add {ip}/24 dev {interface_name}\n"
            script += "if [ $? -eq 0 ]; then\n"
            script += f"    echo 'SUCCESS: Added {ip}'\n"
            script += "else\n"
            script += f"    echo 'WARNING: Failed to add {ip} (may already exist)'\n"
            script += "fi\n"
            script += "echo ''\n\n"
        
        script += "echo '========================================'\n"
        script += "echo 'Configuration complete!'\n"
        script += "echo '========================================'\n"
        script += "echo 'Note: These IPs are temporary and will be lost on reboot'\n"
        script += "echo 'To make permanent, add to /etc/network/interfaces or use NetworkManager'\n"
        
        return script
    
    @staticmethod
    def generate_macos_shell(ip_addresses: List[str], interface_name: str = "en0") -> str:
        """
        Generate macOS shell script to configure IP addresses
        
        Args:
            ip_addresses: List of IP addresses to configure
            interface_name: Network interface name
            
        Returns:
            Shell script content
        """
        script = "#!/bin/bash\n"
        script += "# SCADA Scout - Network Configuration Script\n"
        script += "# Generated for macOS\n"
        script += "# Run with: sudo bash this_script.sh\n\n"
        
        script += "echo '========================================'\n"
        script += "echo 'SCADA Scout Network Configuration'\n"
        script += "echo '========================================'\n"
        script += "echo ''\n\n"
        
        script += "# Check for root privileges\n"
        script += "if [ \"$EUID\" -ne 0 ]; then\n"
        script += "    echo 'ERROR: This script must be run as root'\n"
        script += "    echo 'Please run: sudo bash $0'\n"
        script += "    exit 1\n"
        script += "fi\n\n"
        
        script += f"echo 'Configuring {len(ip_addresses)} IP address(es) on interface: {interface_name}'\n"
        script += "echo ''\n\n"
        
        for i, ip in enumerate(ip_addresses):
            if ip in ["127.0.0.1", "0.0.0.0"] or not NetworkUtils.validate_ip_address(ip):
                continue
            
            script += f"echo '[{i+1}/{len(ip_addresses)}] Adding IP: {ip}'\n"
            script += f"ifconfig {interface_name} alias {ip} netmask 255.255.255.0\n"
            script += "if [ $? -eq 0 ]; then\n"
            script += f"    echo 'SUCCESS: Added {ip}'\n"
            script += "else\n"
            script += f"    echo 'WARNING: Failed to add {ip}'\n"
            script += "fi\n"
            script += "echo ''\n\n"
        
        script += "echo '========================================'\n"
        script += "echo 'Configuration complete!'\n"
        script += "echo '========================================'\n"
        script += "echo 'Note: These IPs are temporary and will be lost on reboot'\n"
        script += "echo 'To make permanent, configure in Network Preferences'\n"
        
        return script
