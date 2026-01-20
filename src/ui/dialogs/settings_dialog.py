"""
Settings Dialog for customizing SCADA Scout appearance and behavior.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QComboBox, QSpinBox, QGroupBox,
    QFormLayout, QColorDialog, QFontComboBox, QCheckBox,
    QDialogButtonBox, QMessageBox, QApplication, QPlainTextEdit
)
from PySide6.QtCore import Qt, QSettings, Signal, QTimer, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
import sys
import shutil
import subprocess
import shlex
import tempfile
import os
import stat


class SettingsDialog(QDialog):
    """Dialog for customizing application appearance and settings."""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Application Settings")
        self.resize(950, 720)
        self.setMinimumSize(900, 680)
        
        self.settings = QSettings("ScadaScout", "UI")
        self._setup_ui()
        self._load_settings()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tab widget for different setting categories
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Appearance tab
        self.appearance_tab = self._create_appearance_tab()
        self.tabs.addTab(self.appearance_tab, "🎨 Appearance")
        
        # Typography tab
        self.typography_tab = self._create_typography_tab()
        self.tabs.addTab(self.typography_tab, "🔤 Typography")
        
        # Colors tab
        self.colors_tab = self._create_colors_tab()
        self.tabs.addTab(self.colors_tab, "🌈 Colors")
        
        # Layout tab
        self.layout_tab = self._create_layout_tab()
        self.tabs.addTab(self.layout_tab, "📐 Layout")
        
        # Guides & Setup tab
        self.guides_tab = self._create_guides_tab()
        self.tabs.addTab(self.guides_tab, "📖 Guides & Setup")

        # Network / Packet Capture tab
        self.network_tab = self._create_network_tab()
        self.tabs.addTab(self.network_tab, "🌐 Network")
        
        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.RestoreDefaults | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.RestoreDefaults).clicked.connect(self._restore_defaults)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self._apply_now)
        layout.addWidget(button_box)

        # Live-apply changes without clicking Apply
        self._live_apply_timer = QTimer(self)
        self._live_apply_timer.setSingleShot(True)
        self._live_apply_timer.timeout.connect(self._apply_now)
        self._wire_live_apply()
        
    def _create_appearance_tab(self):
        """Create the appearance settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Theme selection
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout(theme_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["IED Scout-like", "Windows 11", "iOS Style", "Professional (Light)", "Dark", "Custom"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addRow("Color Theme:", self.theme_combo)

        # Use custom colors (enabled automatically when theme = Custom)
        self.use_custom_colors = QCheckBox("Use custom colors (from Colors tab)")
        self.use_custom_colors.setChecked(False)
        theme_layout.addRow("", self.use_custom_colors)
        
        # Capture backend preference moved to Network tab (keeps Appearance focused)
        
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Modern", "Classic", "Flat"])
        theme_layout.addRow("Style:", self.style_combo)
        
        layout.addWidget(theme_group)
        
        # Window settings
        window_group = QGroupBox("Window Appearance")
        window_layout = QFormLayout(window_group)
        
        self.window_opacity = QSpinBox()
        self.window_opacity.setRange(50, 100)
        self.window_opacity.setValue(100)
        self.window_opacity.setSuffix("%")
        window_layout.addRow("Window Opacity:", self.window_opacity)
        
        self.show_icons = QCheckBox("Show icons in menus")
        self.show_icons.setChecked(True)
        window_layout.addRow("", self.show_icons)
        
        self.animations_enabled = QCheckBox("Enable animations")
        self.animations_enabled.setChecked(True)
        window_layout.addRow("", self.animations_enabled)
        
        layout.addWidget(window_group)
        layout.addStretch()
        
        return widget
        
    def _create_typography_tab(self):
        """Create the typography settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Font settings
        font_group = QGroupBox("Font Settings")
        font_layout = QFormLayout(font_group)
        
        self.font_family = QFontComboBox()
        font_layout.addRow("Font Family:", self.font_family)
        

        
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 20)
        self.font_size.setValue(10)
        self.font_size.setSuffix(" pt")
        font_layout.addRow("Font Size:", self.font_size)
        
        self.monospace_font = QFontComboBox()
        self.monospace_font.setFontFilters(QFontComboBox.MonospacedFonts)
        font_layout.addRow("Console Font:", self.monospace_font)
        
        self.monospace_size = QSpinBox()
        self.monospace_size.setRange(8, 16)
        self.monospace_size.setValue(10)
        self.monospace_size.setSuffix(" pt")
        font_layout.addRow("Console Font Size:", self.monospace_size)
        
        layout.addWidget(font_group)
        
        # Text rendering
        render_group = QGroupBox("Text Rendering")
        render_layout = QFormLayout(render_group)
        
        self.antialiasing = QCheckBox("Enable antialiasing")
        self.antialiasing.setChecked(True)
        render_layout.addRow("", self.antialiasing)
        
        self.subpixel = QCheckBox("Enable subpixel rendering")
        self.subpixel.setChecked(True)
        render_layout.addRow("", self.subpixel)
        
        layout.addWidget(render_group)
        layout.addStretch()
        
        return widget
        
    def _create_colors_tab(self):
        """Create the colors customization tab."""
        from PySide6.QtWidgets import QGridLayout
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Primary colors in 3-column grid
        primary_group = QGroupBox("Primary Colors")
        primary_layout = QGridLayout(primary_group)
        primary_layout.setVerticalSpacing(12)
        primary_layout.setHorizontalSpacing(10)
        primary_layout.setContentsMargins(15, 15, 15, 15)
        
        # Row 0
        self.primary_color = self._create_color_button("#3498db")
        primary_layout.addWidget(QLabel("Primary:"), 0, 0, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.primary_color, 0, 1, 1, 1)
        
        self.accent_color = self._create_color_button("#1abc9c")
        primary_layout.addWidget(QLabel("Accent:"), 0, 2, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.accent_color, 0, 3, 1, 1)
        
        self.success_color = self._create_color_button("#27ae60")
        primary_layout.addWidget(QLabel("Success:"), 0, 4, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.success_color, 0, 5, 1, 1)
        
        # Row 1
        self.warning_color = self._create_color_button("#f39c12")
        primary_layout.addWidget(QLabel("Warning:"), 1, 0, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.warning_color, 1, 1, 1, 1)
        
        self.error_color = self._create_color_button("#e74c3c")
        primary_layout.addWidget(QLabel("Error:"), 1, 2, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.error_color, 1, 3, 1, 1)

        self.text_color = self._create_color_button("#2c3e50")
        primary_layout.addWidget(QLabel("Text:"), 1, 4, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.text_color, 1, 5, 1, 1)

        # Row 2
        self.menu_bar_color = self._create_color_button("#2c3e50")
        primary_layout.addWidget(QLabel("Menu Bar:"), 2, 0, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.menu_bar_color, 2, 1, 1, 1)

        self.dock_title_color = self._create_color_button("#3498db")
        primary_layout.addWidget(QLabel("Dock Title:"), 2, 2, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.dock_title_color, 2, 3, 1, 1)

        self.header_color = self._create_color_button("#34495e")
        primary_layout.addWidget(QLabel("Header:"), 2, 4, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.header_color, 2, 5, 1, 1)

        # Row 3
        self.status_bar_color = self._create_color_button("#34495e")
        primary_layout.addWidget(QLabel("Status Bar:"), 3, 0, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.status_bar_color, 3, 1, 1, 1)

        self.toolbar_color = self._create_color_button("#34495e")
        primary_layout.addWidget(QLabel("Toolbar:"), 3, 2, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.toolbar_color, 3, 3, 1, 1)

        self.selection_color = self._create_color_button("#3498db")
        primary_layout.addWidget(QLabel("Selection:"), 3, 4, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.selection_color, 3, 5, 1, 1)

        # Row 4
        self.selection_text_color = self._create_color_button("#ffffff")
        primary_layout.addWidget(QLabel("Selection Text:"), 4, 0, 1, 1, Qt.AlignRight)
        primary_layout.addWidget(self.selection_text_color, 4, 1, 1, 1)
        
        # Add stretch to remaining columns to prevent excessive spacing
        primary_layout.setColumnStretch(6, 1)
        
        layout.addWidget(primary_group)
        
        # Background colors
        bg_group = QGroupBox("Background Colors")
        bg_layout = QFormLayout(bg_group)
        bg_layout.setVerticalSpacing(10)
        bg_layout.setHorizontalSpacing(15)
        
        self.bg_main = self._create_color_button("#f5f6f7")
        bg_layout.addRow("Main Background:", self.bg_main)
        
        self.bg_widget = self._create_color_button("#ffffff")
        bg_layout.addRow("Widget Background:", self.bg_widget)
        
        self.bg_alternate = self._create_color_button("#f8f9fa")
        bg_layout.addRow("Alternate Background:", self.bg_alternate)
        
        layout.addWidget(bg_group)
        layout.addStretch()
        
        return widget
        
    def _create_layout_tab(self):
        """Create the layout settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Spacing settings
        spacing_group = QGroupBox("Spacing & Padding")
        spacing_layout = QFormLayout(spacing_group)
        
        self.widget_padding = QSpinBox()
        self.widget_padding.setRange(2, 20)
        self.widget_padding.setValue(8)
        self.widget_padding.setSuffix(" px")
        spacing_layout.addRow("Widget Padding:", self.widget_padding)
        
        self.button_padding = QSpinBox()
        self.button_padding.setRange(4, 24)
        self.button_padding.setValue(8)
        self.button_padding.setSuffix(" px")
        spacing_layout.addRow("Button Padding:", self.button_padding)
        
        # Border radius for rounded corners (create the widget here)
        self.border_radius = QSpinBox()
        self.border_radius.setRange(0, 24)
        self.border_radius.setValue(4)
        self.border_radius.setSuffix(" px")
        spacing_layout.addRow("Border Radius:", self.border_radius)
        
        self.auto_save_layout = QCheckBox("Auto-save window layout on exit")
        self.auto_save_layout.setChecked(True)
        spacing_layout.addRow("", self.auto_save_layout)

        # Copy behavior
        self.copy_tag_tokenized = QCheckBox("Copy tag addresses as script tokens ({{TAG:...}})")
        self.copy_tag_tokenized.setToolTip(
            "When enabled, 'Copy Tag Address' will place a tokenized value like {{TAG:Device::Addr}}\n"
            "which is ready to paste into the Python script editor. Disable to copy raw unique addresses."
        )
        self.copy_tag_tokenized.setChecked(True)
        spacing_layout.addRow("", self.copy_tag_tokenized)
        
        layout.addWidget(spacing_group)
        
        # Size settings
        size_group = QGroupBox("Component Sizes")
        size_layout = QFormLayout(size_group)
        
        self.button_height = QSpinBox()
        self.button_height.setRange(24, 48)
        self.button_height.setValue(32)
        self.button_height.setSuffix(" px")
        size_layout.addRow("Button Height:", self.button_height)
        
        self.input_height = QSpinBox()
        self.input_height.setRange(24, 48)
        self.input_height.setValue(32)
        self.input_height.setSuffix(" px")
        size_layout.addRow("Input Height:", self.input_height)
        
        self.icon_size = QSpinBox()
        self.icon_size.setRange(16, 48)
        self.icon_size.setValue(24)
        self.icon_size.setSuffix(" px")
        size_layout.addRow("Icon Size:", self.icon_size)
        
        layout.addWidget(size_group)
        layout.addStretch()
        
        return widget
        
    def _create_guides_tab(self):
        """Create the guides and setup tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Comprehensive guide text
        guide_text = QPlainTextEdit()
        guide_text.setReadOnly(True)
        guide_text.setPlainText(self._get_comprehensive_guide())
        layout.addWidget(guide_text)
        
        return widget

    def _create_network_tab(self):
        """Create the network/packet capture settings tab."""
        try:
            from src.ui.dialogs.network_settings_panel import NetworkSettingsPanel
        except Exception:
            # Fallback inline implementation if import fails
            panel = QWidget()
            return panel

        panel = NetworkSettingsPanel()

        # Wire up actions
        panel._refresh_btn.clicked.connect(self._update_setcap_text)
        panel._setcap_btn.clicked.connect(self._copy_setcap_commands)
        panel._open_terminal_btn.clicked.connect(self._open_terminal_with_commands)

        # Keep a reference for load/save
        self.capture_backend = panel.capture_backend
        self._setcap_text = panel._setcap_text
        self._dumpcap_warning_label = panel._dumpcap_warning_label
        # Defaults
        self.default_filter = panel.default_filter
        self.default_iface = panel.default_iface
        self.default_log_to_file = panel.default_log_to_file
        self.default_log_path = panel.default_log_path
        self.default_json = panel.default_json
        self.default_max_mb = panel.default_max_mb
        self.default_max_files = panel.default_max_files

        return panel
        
    def _get_comprehensive_guide(self):
        """Return comprehensive setup and configuration guide."""
        guide = """SCADA Scout Setup and Configuration Guide
==============================================

This guide covers all required setup steps for SCADA Scout, including packet capture configuration, dependencies, and troubleshooting.

1. Prerequisites
----------------
- Python 3.8+ with PySide6, scapy, pymodbus, and other dependencies (see requirements.txt)
- For packet capture: Wireshark/dumpcap or Npcap (on Windows)
- Linux/macOS: Ability to run setcap (for non-root capture)

2. Packet Capture Setup (Critical for Network Monitoring)
----------------------------------------------------------
SCADA Scout uses scapy for packet capture. To avoid running the GUI as root:

Preferred Method (Linux/macOS):
- Install Wireshark: sudo apt install wireshark (Debian/Ubuntu) or equivalent
- Grant capture capabilities to dumpcap:
  sudo setcap 'cap_net_raw,cap_net_admin+eip' "$(which dumpcap)"
- Verify: getcap "$(which dumpcap)" should show capabilities

Alternative (if dumpcap not available):
- Grant capabilities to the Python interpreter:
  sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/bin/python3.12
  (Replace with your actual Python path: python -c "import sys; print(sys.executable)")

Windows:
- Install Npcap from https://nmap.org/npcap/
- Run SCADA Scout as normal user (Npcap handles permissions)

3. Application Configuration
----------------------------
- Theme: Choose Dark, Professional, or Custom in Appearance tab
- Capture Backend: Auto (recommended), AsyncSniffer, or dumpcap
- Fonts and Colors: Customize in Typography and Colors tabs
- Layout: Adjust spacing and sizes in Layout tab

4. Running the Application
--------------------------
- Activate venv: source venv/bin/activate
- Run: python src/main.py
- Do NOT run as root (sudo) unless absolutely necessary

5. Troubleshooting Packet Capture
----------------------------------
- If capture fails: Check dumpcap installation and setcap
- Error "insufficient privileges": Run setcap commands above
- On Linux: Ensure no SELinux/AppArmor blocks setcap
- Test capture: Start capture in UI, generate some network traffic

6. Protocol Support
-------------------
- Modbus TCP: Automatic discovery and polling
- IEC 61850: Requires libiec61850 (see IEC61850_SETUP.md)
- Packet capture: For diagnostics and monitoring

7. Development and Testing
--------------------------
- Headless testing: Use DeviceManagerCore directly
- Logs: Check event log for errors
- Dependencies: pip install -r requirements.txt

For more details, see README.md and docs/ folder.
"""
        return guide
        
    def _create_color_button(self, default_color):
        """Create a button for color selection."""
        button = QPushButton()
        button.setFixedSize(160, 36)
        button.setProperty("color", default_color)
        self._update_color_button(button, default_color)
        button.clicked.connect(lambda: self._choose_color(button))
        return button
        
    def _update_color_button(self, button, color):
        """Update color button appearance using an icon (no stylesheet)."""
        try:
            pix = QPixmap(32, 32)
            pix.fill(QColor(color))
            # Draw a subtle border so the swatch is visible on light backgrounds
            # (QPixmap.fill replaces the content; small border handled by icon padding)
            icon = QIcon(pix)
            button.setIcon(icon)
            button.setIconSize(QSize(32, 32))
        except Exception:
            button.setIcon(QIcon())
        button.setText(color)
        button.setToolTip(color)
        
    def _choose_color(self, button):
        """Open color picker dialog."""
        current_color = QColor(button.property("color"))
        color = QColorDialog.getColor(current_color, self, "Choose Color")
        if color.isValid():
            color_hex = color.name()
            button.setProperty("color", color_hex)
            self._update_color_button(button, color_hex)
            self._schedule_apply()
            
    def _load_settings(self):
        """Load saved settings."""
        # Appearance
        self.theme_combo.setCurrentText(self.settings.value("theme", "IED Scout-like"))
        self.use_custom_colors.setChecked(self.settings.value("use_custom_colors", False, type=bool))
        # capture_backend moved to Network tab
        try:
            self.capture_backend.setCurrentText(self.settings.value("capture_backend", "Auto"))
        except Exception:
            pass
        self.style_combo.setCurrentText(self.settings.value("style", "Modern"))
        self.window_opacity.setValue(int(self.settings.value("window_opacity", 100)))
        self.show_icons.setChecked(self.settings.value("show_icons", True, type=bool))
        self.animations_enabled.setChecked(self.settings.value("animations_enabled", True, type=bool))
        
        # Typography
        font_family = self.settings.value("font_family", "Segoe UI")
        index = self.font_family.findText(font_family)
        if index >= 0:
            self.font_family.setCurrentIndex(index)
        self.font_size.setValue(int(self.settings.value("font_size", 10)))
        
        mono_font = self.settings.value("monospace_font", "Consolas")
        index = self.monospace_font.findText(mono_font)
        if index >= 0:
            self.monospace_font.setCurrentIndex(index)
        self.monospace_size.setValue(int(self.settings.value("monospace_size", 10)))
        
        self.antialiasing.setChecked(self.settings.value("antialiasing", True, type=bool))
        self.subpixel.setChecked(self.settings.value("subpixel", True, type=bool))
        
        # Colors
        self._update_color_button(self.primary_color, self.settings.value("primary_color", "#3498db"))
        self._update_color_button(self.accent_color, self.settings.value("accent_color", "#1abc9c"))
        self._update_color_button(self.success_color, self.settings.value("success_color", "#27ae60"))
        self._update_color_button(self.warning_color, self.settings.value("warning_color", "#f39c12"))
        self._update_color_button(self.error_color, self.settings.value("error_color", "#e74c3c"))
        self._update_color_button(self.text_color, self.settings.value("text_color", "#2c3e50"))
        self._update_color_button(self.menu_bar_color, self.settings.value("menu_bar_color", "#2c3e50"))
        self._update_color_button(self.dock_title_color, self.settings.value("dock_title_color", "#3498db"))
        self._update_color_button(self.header_color, self.settings.value("header_color", "#34495e"))
        self._update_color_button(self.status_bar_color, self.settings.value("status_bar_color", "#34495e"))
        self._update_color_button(self.toolbar_color, self.settings.value("toolbar_color", "#34495e"))
        self._update_color_button(self.selection_color, self.settings.value("selection_color", "#3498db"))
        self._update_color_button(self.selection_text_color, self.settings.value("selection_text_color", "#ffffff"))
        self._update_color_button(self.bg_main, self.settings.value("bg_main", "#f5f6f7"))
        self._update_color_button(self.bg_widget, self.settings.value("bg_widget", "#ffffff"))
        self._update_color_button(self.bg_alternate, self.settings.value("bg_alternate", "#f8f9fa"))
        
        # Layout
        self.widget_padding.setValue(int(self.settings.value("widget_padding", 8)))
        self.button_padding.setValue(int(self.settings.value("button_padding", 8)))
        self.border_radius.setValue(int(self.settings.value("border_radius", 4)))
        self.auto_save_layout.setChecked(self.settings.value("auto_save_layout", True, type=bool))
        self.button_height.setValue(int(self.settings.value("button_height", 32)))
        self.input_height.setValue(int(self.settings.value("input_height", 32)))
        self.icon_size.setValue(int(self.settings.value("icon_size", 24)))

        # Copy behavior preference
        try:
            self.copy_tag_tokenized.setChecked(self.settings.value("copy_tag_tokenized", True, type=bool))
        except Exception:
            try:
                self.copy_tag_tokenized.setChecked(True)
            except Exception:
                pass

        # Network / Capture defaults
        try:
            # Default filter stored as BPF string (or label)
            saved_filter = self.settings.value("capture_default_filter", "All Traffic")
            idx = self.default_filter.findText(saved_filter)
            if idx >= 0:
                self.default_filter.setCurrentIndex(idx)
        except Exception:
            pass

        try:
            self.default_iface.setText(self.settings.value("capture_default_iface", ""))
            self.default_log_to_file.setChecked(self.settings.value("capture_default_log", False, type=bool))
            self.default_log_path.setText(self.settings.value("capture_default_log_path", "packets.log"))
            self.default_json.setChecked(self.settings.value("capture_default_json", False, type=bool))
            self.default_max_mb.setValue(int(self.settings.value("capture_default_max_mb", 10)))
            self.default_max_files.setValue(int(self.settings.value("capture_default_max_files", 5)))
        except Exception:
            pass

        # update setcap commands display
        try:
            self._update_setcap_text()
        except Exception:
            pass

        # show/hide dumpcap inline warning; do NOT auto-open separate dialogs —
        # keep everything within the Network tab to avoid duplicate windows.
        try:
            dumpcap_path = shutil.which('dumpcap')
            if not dumpcap_path:
                # show inline warning
                self._dumpcap_warning_label.setText(
                    "dumpcap not found on PATH — install Wireshark/dumpcap or use the Copy setcap button."
                )
                self._dumpcap_warning_label.setProperty("class", "status")
                self._dumpcap_warning_label.setProperty("status", "warning")
                self._dumpcap_warning_label.style().unpolish(self._dumpcap_warning_label)
                self._dumpcap_warning_label.style().polish(self._dumpcap_warning_label)
                self._dumpcap_warning_label.setVisible(True)
            else:
                self._dumpcap_warning_label.setVisible(False)
        except Exception:
            try:
                self._dumpcap_warning_label.setVisible(False)
            except Exception:
                pass
        
    def _save_settings(self):
        """Save current settings."""
        # Appearance
        self.settings.setValue("theme", self.theme_combo.currentText())
        # Enable custom colors when theme is Custom or checkbox is checked
        use_custom = (self.theme_combo.currentText() == "Custom") or self.use_custom_colors.isChecked()
        self.settings.setValue("use_custom_colors", use_custom)
        self.settings.setValue("capture_backend", self.capture_backend.currentText())
        self.settings.setValue("style", self.style_combo.currentText())
        self.settings.setValue("window_opacity", self.window_opacity.value())
        self.settings.setValue("show_icons", self.show_icons.isChecked())
        self.settings.setValue("animations_enabled", self.animations_enabled.isChecked())
        
        # Typography
        self.settings.setValue("font_family", self.font_family.currentText())
        self.settings.setValue("font_size", self.font_size.value())
        self.settings.setValue("monospace_font", self.monospace_font.currentText())
        self.settings.setValue("monospace_size", self.monospace_size.value())
        self.settings.setValue("antialiasing", self.antialiasing.isChecked())
        self.settings.setValue("subpixel", self.subpixel.isChecked())
        
        # Colors
        self.settings.setValue("primary_color", self.primary_color.property("color"))
        self.settings.setValue("accent_color", self.accent_color.property("color"))
        self.settings.setValue("success_color", self.success_color.property("color"))
        self.settings.setValue("warning_color", self.warning_color.property("color"))
        self.settings.setValue("error_color", self.error_color.property("color"))
        self.settings.setValue("text_color", self.text_color.property("color"))
        self.settings.setValue("menu_bar_color", self.menu_bar_color.property("color"))
        self.settings.setValue("dock_title_color", self.dock_title_color.property("color"))
        self.settings.setValue("header_color", self.header_color.property("color"))
        self.settings.setValue("status_bar_color", self.status_bar_color.property("color"))
        self.settings.setValue("toolbar_color", self.toolbar_color.property("color"))
        self.settings.setValue("selection_color", self.selection_color.property("color"))
        self.settings.setValue("selection_text_color", self.selection_text_color.property("color"))
        self.settings.setValue("bg_main", self.bg_main.property("color"))
        self.settings.setValue("bg_widget", self.bg_widget.property("color"))
        self.settings.setValue("bg_alternate", self.bg_alternate.property("color"))
        
        # Layout
        self.settings.setValue("widget_padding", self.widget_padding.value())
        self.settings.setValue("button_padding", self.button_padding.value())
        self.settings.setValue("border_radius", self.border_radius.value())
        self.settings.setValue("auto_save_layout", self.auto_save_layout.isChecked())
        self.settings.setValue("button_height", self.button_height.value())
        self.settings.setValue("input_height", self.input_height.value())
        self.settings.setValue("icon_size", self.icon_size.value())
        # Copy behavior preference
        try:
            self.settings.setValue("copy_tag_tokenized", self.copy_tag_tokenized.isChecked())
        except Exception:
            pass
        
        self.settings.sync()
        # Save network defaults
        try:
            self.settings.setValue("capture_default_filter", self.default_filter.currentText())
            self.settings.setValue("capture_default_iface", self.default_iface.text())
            self.settings.setValue("capture_default_log", self.default_log_to_file.isChecked())
            self.settings.setValue("capture_default_log_path", self.default_log_path.text())
            self.settings.setValue("capture_default_json", self.default_json.isChecked())
            self.settings.setValue("capture_default_max_mb", self.default_max_mb.value())
            self.settings.setValue("capture_default_max_files", self.default_max_files.value())
        except Exception:
            pass
        
    def _restore_defaults(self):
        """Restore default settings."""
        reply = QMessageBox.question(
            self,
            "Restore Defaults",
            "Are you sure you want to restore all settings to their default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.settings.clear()
            self._load_settings()
            QMessageBox.information(self, "Settings Restored", "Default settings have been restored.")
            self._schedule_apply()

    def _build_setcap_commands(self) -> str:
        """Build a small help text with exact setcap commands for dumpcap and current python executable."""
        parts = []
        dumpcap_path = shutil.which('dumpcap')
        try:
            py = os.path.realpath(sys.executable)
        except Exception:
            py = sys.executable
        
        parts.append("# Recommended: grant capture capabilities to dumpcap (preferred)")
        if dumpcap_path:
            parts.append(f"sudo setcap 'cap_net_raw,cap_net_admin+eip' {dumpcap_path}")
        else:
            parts.append("# dumpcap not found on PATH. Install Wireshark/dumpcap, then run:")
            parts.append("# On Debian/Ubuntu: sudo apt install wireshark")
            parts.append("# On Fedora: sudo dnf install wireshark-cli")
            parts.append("# After installing, run setcap on /usr/bin/dumpcap (or the installed path):")
            parts.append("sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/bin/dumpcap")
        
        parts.append("")
        parts.append("# Alternative (less preferred): grant capture to the Python interpreter")

    def _copy_setcap_commands(self):
        """Copy generated setcap commands to clipboard and notify the user."""
        try:
            txt = self._build_setcap_commands()
            cb = QApplication.clipboard()
            cb.setText(txt)
            QMessageBox.information(self, "Copied", "Setcap commands copied to clipboard.")
        except Exception as e:
            QMessageBox.warning(self, "Copy Failed", f"Unable to copy commands: {e}")

    def _update_setcap_text(self):
        """Refresh the read-only setcap commands display."""
        try:
            txt = self._build_setcap_commands()
            self._setcap_text.setPlainText(txt)
        except Exception:
            self._setcap_text.setPlainText("Unable to generate commands on this system.")

    def _show_terminal_snippet_dialog(self):
        """Show a dialog containing the exact setcap commands for copying."""
        try:
            txt = self._build_setcap_commands()

            dlg = QDialog(self)
            dlg.setWindowTitle("Setcap Commands — Copy to Terminal")
            dlg.resize(700, 340)
            v = QVBoxLayout(dlg)

            te = QPlainTextEdit()
            te.setPlainText(txt)
            te.setReadOnly(True)
            te.setFixedHeight(220)
            v.addWidget(te)

            btn_row = QWidget()
            btn_layout = QHBoxLayout(btn_row)
            btn_layout.setContentsMargins(0, 0, 0, 0)

            copy_btn = QPushButton("Copy to clipboard")
            def _do_copy():
                QApplication.clipboard().setText(txt)
                QMessageBox.information(dlg, "Copied", "Commands copied to clipboard.")
            copy_btn.clicked.connect(_do_copy)
            btn_layout.addWidget(copy_btn)

            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dlg.accept)
            btn_layout.addWidget(close_btn)

            v.addWidget(btn_row)

            dlg.exec()
        except Exception:
            pass

    def _open_terminal_with_commands(self):
        """Try to open a terminal emulator and paste the setcap commands into it."""
        try:
            txt = self._build_setcap_commands()

            # Write commands to a temporary shell script to avoid quoting issues
            fd, script_path = tempfile.mkstemp(prefix='scadascout_setcap_', suffix='.sh', text=True)
            try:
                with os.fdopen(fd, 'w') as f:
                    f.write('#!/usr/bin/env bash\n')
                    f.write('set -euo pipefail\n')
                    f.write('\n')
                    for line in txt.splitlines():
                        f.write(line + '\n')
                    f.write('\n')
                    f.write('echo ""\n')
                    f.write('echo "--- Commands finished. Press Enter to close this terminal. ---"\n')
                    f.write('read -r\n')
                os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR)

                cands = [
                    'x-terminal-emulator', 'gnome-terminal', 'konsole', 'xfce4-terminal',
                    'xterm', 'mate-terminal', 'terminator', 'alacritty', 'kitty'
                ]

                found = False
                for name in cands:
                    path = shutil.which(name)
                    if not path:
                        continue
                    if name == 'xterm':
                        args = [path, '-hold', '-e', f"bash -ic {shlex.quote(f'bash {script_path}; exec bash')}" ]
                    elif name in ('gnome-terminal', 'mate-terminal'):
                        args = [path, '--', 'bash', '-ic', f"bash {script_path}; exec bash"]
                    elif name == 'konsole':
                        args = [path, '-e', 'bash', '-ic', f"bash {script_path}; exec bash"]
                    elif name == 'xfce4-terminal':
                        args = [path, '--hold', '-e', f"bash -ic {shlex.quote(f'bash {script_path}; exec bash')}" ]
                    else:
                        args = [path, '-e', 'bash', '-ic', f"bash {script_path}; exec bash"]

                    try:
                        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
                        found = True
                        break
                    except Exception:
                        continue

                if not found:
                    self._show_terminal_snippet_dialog()
            except Exception:
                try:
                    os.unlink(script_path)
                except Exception:
                    pass
                raise
            finally:
                # Leave the temp script for the terminal to use; OS temp cleanup will handle it later.
                pass
        except Exception:
            try:
                self._show_terminal_snippet_dialog()
            except Exception:
                pass
            
    def accept(self):
        """Save settings and close dialog."""
        self._save_settings()
        self.settings_changed.emit()
        super().accept()

    def _apply_now(self):
        """Apply settings immediately without closing the dialog."""
        self._save_settings()
        self.settings_changed.emit()

    def _schedule_apply(self):
        """Debounced apply for live changes."""
        try:
            self._live_apply_timer.start(150)
        except Exception:
            self._apply_now()

    def _wire_live_apply(self):
        """Connect controls to live-apply changes."""
        # Appearance
        self.theme_combo.currentIndexChanged.connect(self._schedule_apply)
        self.use_custom_colors.stateChanged.connect(self._schedule_apply)
        self.style_combo.currentIndexChanged.connect(self._schedule_apply)
        self.window_opacity.valueChanged.connect(self._schedule_apply)
        self.show_icons.stateChanged.connect(self._schedule_apply)
        self.animations_enabled.stateChanged.connect(self._schedule_apply)

        # Typography
        try:
            self.font_family.currentFontChanged.connect(self._schedule_apply)
        except Exception:
            self.font_family.currentIndexChanged.connect(self._schedule_apply)
        self.font_size.valueChanged.connect(self._schedule_apply)
        try:
            self.monospace_font.currentFontChanged.connect(self._schedule_apply)
        except Exception:
            self.monospace_font.currentIndexChanged.connect(self._schedule_apply)
        self.monospace_size.valueChanged.connect(self._schedule_apply)
        self.antialiasing.stateChanged.connect(self._schedule_apply)
        self.subpixel.stateChanged.connect(self._schedule_apply)

        # Layout
        self.widget_padding.valueChanged.connect(self._schedule_apply)
        self.button_padding.valueChanged.connect(self._schedule_apply)
        self.border_radius.valueChanged.connect(self._schedule_apply)
        self.auto_save_layout.stateChanged.connect(self._schedule_apply)
        self.button_height.valueChanged.connect(self._schedule_apply)
        self.input_height.valueChanged.connect(self._schedule_apply)
        self.icon_size.valueChanged.connect(self._schedule_apply)

        # Colors tab
        self.primary_color.clicked.connect(self._schedule_apply)
        self.accent_color.clicked.connect(self._schedule_apply)
        self.success_color.clicked.connect(self._schedule_apply)
        self.warning_color.clicked.connect(self._schedule_apply)
        self.error_color.clicked.connect(self._schedule_apply)
        self.text_color.clicked.connect(self._schedule_apply)
        self.menu_bar_color.clicked.connect(self._schedule_apply)
        self.dock_title_color.clicked.connect(self._schedule_apply)
        self.header_color.clicked.connect(self._schedule_apply)
        self.status_bar_color.clicked.connect(self._schedule_apply)
        self.toolbar_color.clicked.connect(self._schedule_apply)
        self.selection_color.clicked.connect(self._schedule_apply)
        self.selection_text_color.clicked.connect(self._schedule_apply)
        self.bg_main.clicked.connect(self._schedule_apply)
        self.bg_widget.clicked.connect(self._schedule_apply)
        self.bg_alternate.clicked.connect(self._schedule_apply)

        # Network / capture
        try:
            self.capture_backend.currentIndexChanged.connect(self._schedule_apply)
            self.default_filter.currentIndexChanged.connect(self._schedule_apply)
            self.default_iface.textChanged.connect(self._schedule_apply)
            self.default_log_to_file.stateChanged.connect(self._schedule_apply)
            self.default_log_path.textChanged.connect(self._schedule_apply)
            self.default_json.stateChanged.connect(self._schedule_apply)
            self.default_max_mb.valueChanged.connect(self._schedule_apply)
            self.default_max_files.valueChanged.connect(self._schedule_apply)
        except Exception:
            pass

    def _on_theme_changed(self, theme_name):
        """Update settings based on selected theme."""
        # Define theme defaults
        defaults = {}
        if theme_name == "IED Scout-like":
            defaults = {
                "style": "Modern", 
                "primary_color": "#005baa", 
                "bg_main": "#ffffff",
                "bg_widget": "#ffffff",
                "bg_alternate": "#f8f9fa",
                "widget_padding": 8,
                "button_padding": 8,
                "border_radius": 4
            }
        elif theme_name == "Windows 11":
            defaults = {
                "style": "Modern", 
                "primary_color": "#0067c0", 
                "bg_main": "#f3f3f3",
                "bg_widget": "#ffffff",
                "bg_alternate": "#f0f0f0",
                "widget_padding": 12,
                "button_padding": 10,
                "border_radius": 8
            }
        elif theme_name == "iOS Style":
            defaults = {
                "style": "Flat", 
                "primary_color": "#007aff", 
                "bg_main": "#f2f2f7",
                "bg_widget": "#ffffff",
                "bg_alternate": "#e5e5ea",
                "widget_padding": 10,
                "button_padding": 12,
                "border_radius": 10
            }
        elif theme_name == "Dark":
             defaults = {
                "style": "Modern", 
                "primary_color": "#3498db", 
                "bg_main": "#1e1e1e",
                "bg_widget": "#2d2d2d",
                "bg_alternate": "#252525",
                "widget_padding": 8,
                "button_padding": 8,
                "border_radius": 4
            }
        else: # Professional (Light) or Custom
             defaults = {
                "style": "Modern", 
                "primary_color": "#3498db", 
                "bg_main": "#f5f6f7",
                "bg_widget": "#ffffff",
                "bg_alternate": "#f8f9fa",
                "widget_padding": 8,
                "button_padding": 8,
                "border_radius": 4
            }
            
        # Apply defaults to UI controls if not custom
        if theme_name != "Custom":
            self.use_custom_colors.setChecked(False) # Do not check this automatically to avoid confusing override behavior
            
            # Update Appearance tab
            index = self.style_combo.findText(defaults["style"])
            if index >= 0:
                self.style_combo.setCurrentIndex(index)
            
            # Update Layout Tab
            self.widget_padding.setValue(defaults["widget_padding"])
            self.button_padding.setValue(defaults["button_padding"])
            self.border_radius.setValue(defaults["border_radius"])
                
            # Update Colors tab (populate inputs)
            self._update_color_button(self.primary_color, defaults["primary_color"])
            self._update_color_button(self.bg_main, defaults["bg_main"])
            self._update_color_button(self.bg_widget, defaults["bg_widget"])
            self._update_color_button(self.bg_alternate, defaults["bg_alternate"])
            
            # Set other colors to common defaults
            if theme_name == "Dark":
                self._update_color_button(self.accent_color, "#2980b9")
                self._update_color_button(self.success_color, "#2ecc71")
                self._update_color_button(self.warning_color, "#f1c40f")
                self._update_color_button(self.error_color, "#e74c3c")
            else: # Light themes
                self._update_color_button(self.accent_color, "#1abc9c")
                self._update_color_button(self.success_color, "#27ae60")
                self._update_color_button(self.warning_color, "#f39c12")
                self._update_color_button(self.error_color, "#e74c3c")

        # Trigger a live apply to show changes immediately
        self._live_apply_timer.start(100)
