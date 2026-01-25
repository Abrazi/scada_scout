import sys
import os

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import ctypes

# Early environment sanity checks to avoid loading incompatible system libs (snap/core20)
def _detect_incompatible_system_libs() -> list:
    """Return list of (envvar, value) entries that reference snap/core20 libs."""
    bad = []
    for var in ("LD_LIBRARY_PATH", "LD_PRELOAD"):
        val = os.environ.get(var, "")
        if "/snap/core20" in val or ("/snap" in val and "core" in val):
            bad.append((var, val))
    return bad

# NOTE: GUI and other C-extension imports are intentionally deferred until runtime
# after the environment check — this prevents the dynamic loader from pulling
# in incompatible libraries and producing obscure symbol lookup errors.


logging.basicConfig(level=logging.INFO)

def main():
    """
    Application Entry Point.
    """
    try:
        # Prevent running the GUI with sudo on Linux/Unix: breaks DBus/X11 permissions
        # Windows Administrator mode is safe and sometimes needed (e.g., for port 102)
        def is_running_as_root_on_unix() -> bool:
            """Return True when running with sudo/root on Unix systems.
            
            Windows Administrator mode returns False (safe for GUI apps).
            Only blocks sudo on Linux/Unix where it breaks X11/DBus.
            """
            # Windows: Administrator mode is safe, return False to allow
            if os.name == 'nt':
                return False

            # POSIX: check for root user (UID 0)
            geteuid = getattr(os, 'geteuid', None)
            if callable(geteuid):
                try:
                    return (geteuid() == 0)
                except Exception:
                    return False

            return False

        is_root = is_running_as_root_on_unix()

        if is_root:
            sys.stderr.write("Refusing to run SCADA Scout as root (sudo).\nPlease run without sudo: `source venv/bin/activate && python src/main.py`\n")
            return 1

        # Reduce noisy Qt DBus theme warnings in environments without a session bus
        # (headless sessions or when using sudo). Force a neutral style and silence
        # theme plugin DBus logging which fails under some desktop sandboxes.
        os.environ.setdefault("QT_QPA_PLATFORMTHEME", "")
        os.environ.setdefault("QT_STYLE_OVERRIDE", "Fusion")
        # Silence specific noisy theme plugin messages and Wayland grab warnings
        os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.theme.gnome=false;qt.qpa.theme=false;qt.qpa.wayland=false")

        # Detect and set appropriate Qt platform plugin for Wayland/X11 compatibility
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session_type == "wayland":
            os.environ["QT_QPA_PLATFORM"] = "wayland"
        elif session_type == "x11" or os.environ.get("DISPLAY"):
            os.environ["QT_QPA_PLATFORM"] = "xcb"
        
        # Performance: Use hardware acceleration for graphics if possible
        os.environ.setdefault("QT_QUICK_BACKEND", "software") # Fallback to stable software rendering if needed

        # --- Environment validation (prevent snap/core20 from breaking the native loader) ---
        bad_lib_env = _detect_incompatible_system_libs()
        if bad_lib_env:
            sys.stderr.write("ERROR: Incompatible Snap-provided system libraries detected in your environment.\n")
            sys.stderr.write("This commonly causes: 'undefined symbol: __libc_pthread_init, version GLIBC_PRIVATE'\n\n")
            sys.stderr.write("Detected entries:\n")
            for k, v in bad_lib_env:
                sys.stderr.write(f"  {k}={v}\n")
            sys.stderr.write("\nQuick fixes:\n")
            sys.stderr.write("  1) Run temporarily with cleared env vars:\n")
            sys.stderr.write("       LD_LIBRARY_PATH= LD_PRELOAD= venv/bin/python src/main.py\n")
            sys.stderr.write("  2) Unset the variables in your shell and re-run:\n")
            sys.stderr.write("       unset LD_LIBRARY_PATH; unset LD_PRELOAD; source venv/bin/activate; python src/main.py\n")
            sys.stderr.write("  3) If launched from a .desktop/systemd/IDE, remove the export from that launcher.\n")
            sys.stderr.write("\nIf you want the application to attempt to sanitize these variables automatically, reply and I can add an opt-in flag.\n")
            return 2

        # Defer heavy GUI imports until after env validation to avoid crashing the process
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont
        from src.ui.main_window import MainWindow
        from src.core.device_manager import DeviceManager
        from src.core.app_controller import AppController

        print("Initializing QApplication...")
        app = QApplication(sys.argv)
        app.setApplicationName("Scada Scout")
        
        # Theme and font are applied from saved settings (or defaults) by MainWindow
        
        print("Initializing core components...")
        # Core Logic Initialization
        device_manager = DeviceManager()
        controller = AppController(device_manager)
        
        # No default devices added on startup
        # User must add manually or import SCD
        # Create Main Window
        print("Creating main window...")
        window = MainWindow(device_manager, event_logger=controller.event_logger)
        
        # Connect Python Logging to event log widget
        # Centralized via QtLogHandler which signals the UI
        from src.core.logging_handler import QtLogHandler
        qt_handler = QtLogHandler()
        if hasattr(window, 'event_log_widget'):
            # This is the only place Python logs are connected to the UI
            qt_handler.new_record.connect(window.event_log_widget.log_event)
        
        # Add handler to root logger
        import logging as _logging
        _logging.getLogger().addHandler(qt_handler)
        
        controller.event_logger.info("Application", "SCADA Scout started successfully")
        # Start the controller
        print("Starting controller...")
        controller.start_application()

        # Ensure controller can clean up background threads on exit
        app.aboutToQuit.connect(controller.shutdown)
        
        # Ensure application settings (theme, fonts, sizes) are applied before showing
        try:
            window._apply_settings()
        except Exception:
            pass

        # Show window after everything is initialized
        print("Showing main window...")
        window.show()
        print("Main window shown, starting event loop...")
        
        print("Calling app.exec()...")
        exit_code = app.exec()
        print(f"app.exec() returned with exit code: {exit_code}")
        return exit_code
        
    except Exception as e:
        print(f"Exception in main(): {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    main()
