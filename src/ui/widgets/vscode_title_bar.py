"""
VSCode-style unified title bar with menu bar integration.
Combines window title, menu items, and window controls in one bar.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, 
    QMenuBar, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QSize, QPoint, Signal
from PySide6.QtGui import QIcon, QColor
import os


class VSCodeTitleBar(QWidget):
    """
    Unified title bar combining menu bar and window controls.
    Layout: [App Icon] [Menu Items...] [Spacer] [Title] [Spacer] [Min] [Max] [Close]
    """
    
    # Signals
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._window = parent if parent is not None else self.window()
        
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)
        
        # App icon/title on the left
        self.app_icon = QLabel()
        self.app_icon.setText("📊")  # SCADA Scout icon
        self.app_icon.setStyleSheet("font-size: 16pt; padding: 0 8px;")
        layout.addWidget(self.app_icon)
        
        # Integrated menu bar (takes menu from main window)
        self.menu_bar = QMenuBar(self)
        self.menu_bar.setNativeMenuBar(False)
        self.menu_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }
            QMenuBar::item {
                padding: 8px 12px;
                background-color: transparent;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QMenuBar::item:pressed {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """)
        layout.addWidget(self.menu_bar)
        
        # Spacer
        layout.addStretch()
        
        # Window title in center
        self.title_label = QLabel(self._window.windowTitle() if self._window else "SCADA Scout")
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 11pt;
                font-weight: normal;
                padding: 0 20px;
            }
        """)
        layout.addWidget(self.title_label)
        
        # Spacer
        layout.addStretch()
        
        # Window control buttons on the right
        btn_size = QSize(46, 36)
        
        self.btn_min = QPushButton()
        self.btn_min.setText("−")
        self.btn_min.setFixedSize(btn_size)
        self.btn_min.setFlat(True)
        self.btn_min.setToolTip("Minimize")
        self.btn_min.clicked.connect(self.minimize_clicked.emit)
        self.btn_min.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 16pt;
                font-weight: 300;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        
        self.btn_max = QPushButton()
        self.btn_max.setText("□")
        self.btn_max.setFixedSize(btn_size)
        self.btn_max.setFlat(True)
        self.btn_max.setToolTip("Maximize")
        self.btn_max.clicked.connect(self.maximize_clicked.emit)
        self.btn_max.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 14pt;
                font-weight: 300;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        
        self.btn_close = QPushButton()
        self.btn_close.setText("×")
        self.btn_close.setFixedSize(btn_size)
        self.btn_close.setFlat(True)
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self.close_clicked.emit)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 20pt;
                font-weight: 300;
            }
            QPushButton:hover {
                background-color: #e81123;
                color: white;
            }
        """)
        
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)
        
        # Connect to window title changes
        if self._window:
            try:
                self._window.windowTitleChanged.connect(self._on_window_title_changed)
            except Exception:
                pass
        
        # Apply initial theme
        self._apply_theme()
    
    def _on_window_title_changed(self, title):
        """Update title label when window title changes."""
        self.title_label.setText(title)
    
    def mousePressEvent(self, event):
        """Handle mouse press for window dragging."""
        if event.button() == Qt.LeftButton:
            # Allow dragging only on title bar area (not on menus or buttons)
            widget = self.childAt(event.pos())
            # Only start drag if clicking on the title bar itself, title label, or app icon
            # NOT on menu bar, menu items, or window buttons
            if widget in (self, self.title_label, self.app_icon) or widget is None:
                if self._window and not self._window.isMaximized():
                    self._window.startSystemMove()
                    event.accept()
                    return
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to maximize/restore."""
        if event.button() == Qt.LeftButton:
            widget = self.childAt(event.pos())
            if widget in (self, self.title_label, self.app_icon):
                self.maximize_clicked.emit()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)
    
    def _apply_theme(self):
        """Apply theme colors to title bar."""
        try:
            from src.ui.theme_manager import get_theme_manager
            from src.ui.theme_presets import ColorRole
            
            theme_manager = get_theme_manager()
            
            # Get theme colors
            bg_color = theme_manager.get_color(ColorRole.TOOLBAR_BACKGROUND)
            text_color = theme_manager.get_color(ColorRole.TEXT_PRIMARY)
            border_color = theme_manager.get_color(ColorRole.BORDER)
            
            # Apply to title bar
            self.setStyleSheet(f"""
                VSCodeTitleBar {{
                    background-color: {bg_color};
                    border-bottom: 1px solid {border_color};
                }}
            """)

            # Update menu bar colors (ensure menu text is visible on dark backgrounds)
            try:
                menu_bg = theme_manager.get_color(ColorRole.MENU_BACKGROUND)
                menu_hover = theme_manager.get_color(ColorRole.MENU_HOVER)
                self.menu_bar.setStyleSheet(f"""
                    QMenuBar {{
                        background-color: transparent;
                        border: none;
                        color: {text_color};
                        padding: 0;
                        margin: 0;
                    }}
                    QMenuBar::item {{
                        padding: 8px 12px;
                        background-color: transparent;
                        border-radius: 4px;
                        color: {text_color};
                    }}
                    QMenuBar::item:selected {{
                        background-color: {menu_hover};
                    }}
                    QMenuBar::item:pressed {{
                        background-color: {menu_hover};
                    }}
                    QMenu {{
                        background-color: {menu_bg};
                        color: {text_color};
                        border: 1px solid {border_color};
                    }}
                    QMenu::item:selected {{
                        background-color: {menu_hover};
                    }}
                """)
            except Exception:
                pass
            
            # Update text colors
            self.title_label.setStyleSheet(f"""
                QLabel {{
                    color: {text_color};
                    font-size: 11pt;
                    font-weight: normal;
                    padding: 0 20px;
                }}
            """)
            
            self.app_icon.setStyleSheet(f"""
                QLabel {{
                    color: {text_color};
                    font-size: 16pt;
                    padding: 0 8px;
                }}
            """)
            
            # Update button colors (keeping hover states)
            hover_bg = "rgba(255, 255, 255, 0.1)" if theme_manager.is_dark_theme() else "rgba(0, 0, 0, 0.05)"
            
            self.btn_min.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    color: {text_color};
                    font-size: 16pt;
                    font-weight: 300;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                }}
            """)
            
            self.btn_max.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    color: {text_color};
                    font-size: 14pt;
                    font-weight: 300;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                }}
            """)
            
            self.btn_close.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    color: {text_color};
                    font-size: 20pt;
                    font-weight: 300;
                }}
                QPushButton:hover {{
                    background-color: #e81123;
                    color: white;
                }}
            """)
            
        except Exception as e:
            # Fallback if theme system not available
            pass
    
    def update_theme(self):
        """Public method to update theme."""
        self._apply_theme()
