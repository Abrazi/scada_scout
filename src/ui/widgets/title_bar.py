from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QSize, QPoint, Slot
from PySide6.QtGui import QIcon
import os


class TitleBarWidget(QWidget):
    """A small titlebar widget with minimize / maximize / close buttons.

    This is placed in the menu bar's top-right corner to mimic VSCode
    window controls without replacing the native titlebar.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # parent is expected to be the main window (QMainWindow)
        self._window = parent if parent is not None else self.window()
        self._drag_pos = None

        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Background to match the QMenuBar color from styles.PROFESSIONAL_STYLE
        # Use an exact color so the title area and menu blend seamlessly.
        self.setStyleSheet("background-color: #2c3e50;")
        # Allow custom context menu handling (right-click)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(10)

        btn_size = QSize(26, 26)

        self.btn_min = QPushButton(self)
        self.btn_min.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '..', 'icons', 'minimize.svg')))
        self.btn_min.setFixedSize(btn_size)
        self.btn_min.setToolTip("Minimize")
        self.btn_min.clicked.connect(self._on_minimize)

        self.btn_max = QPushButton(self)
        self._icon_max = QIcon(os.path.join(os.path.dirname(__file__), '..', 'icons', 'maximize.svg'))
        self._icon_restore = QIcon(os.path.join(os.path.dirname(__file__), '..', 'icons', 'restore.svg'))
        self.btn_max.setIcon(self._icon_max)
        self.btn_max.setFixedSize(btn_size)
        self.btn_max.setToolTip("Maximize")
        self.btn_max.clicked.connect(self._on_maximize)

        self.btn_close = QPushButton(self)
        self.btn_close.setIcon(QIcon(os.path.join(os.path.dirname(__file__), '..', 'icons', 'close.svg')))
        self.btn_close.setFixedSize(btn_size)
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self._on_close)

        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setFlat(True)
            b.setCursor(Qt.ArrowCursor)
            # stronger hover colors and visible icons
            if b is self.btn_close:
                b.setStyleSheet("""
                    QPushButton { background: transparent; border: none; }
                    QPushButton:hover { background: #e74c3c; border-radius: 4px; }
                    QPushButton:pressed { background: #c0392b; }
                """)
            else:
                b.setStyleSheet("""
                    QPushButton { background: transparent; border: none; }
                    QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 4px; }
                    QPushButton:pressed { background: rgba(255,255,255,0.14); }
                """)

        # Title label on the left
        self.title_label = QLabel(self._window.windowTitle() if self._window else "")
        self.title_label.setObjectName("TitleBarTitle")
        self.title_label.setStyleSheet("color: #e6e6e6; font-weight: 600; font-size: 11pt;")
        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_max)
        layout.addWidget(self.btn_close)

        # Keep title label in sync with window title
        try:
            if self._window is not None:
                self._window.windowTitleChanged.connect(self._on_window_title_changed)
        except Exception:
            pass

    def contextMenuEvent(self, event):
        # Provide a simple window control menu on right-click (Minimize/Maximize/Close)
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        act_min = menu.addAction("Minimize")
        act_max = menu.addAction("Maximize" if not (self._resolve_window() and self._resolve_window().isMaximized()) else "Restore")
        menu.addSeparator()
        act_close = menu.addAction("Close")

        act_min.triggered.connect(self._on_minimize)
        act_max.triggered.connect(self._on_maximize)
        act_close.triggered.connect(self._on_close)

        menu.popup(event.globalPos())
        event.accept()

    def _on_minimize(self):
        w = self._resolve_window()
        if w:
            w.showMinimized()

    def _on_maximize(self):
        w = self._resolve_window()
        if not w:
            return
        if w.isMaximized():
            w.showNormal()
            self.btn_max.setText("▢")
            self.btn_max.setToolTip("Maximize")
        else:
            w.showMaximized()
            self.btn_max.setText("❐")
            self.btn_max.setToolTip("Restore")

    def _on_close(self):
        w = self._resolve_window()
        if w:
            w.close()

    def _resolve_window(self):
        # prefer explicit parent window if provided
        if isinstance(self._window, QWidget):
            return self._window
        return self.window()

    @Slot(str)
    def _on_window_title_changed(self, title: str):
        try:
            self.title_label.setText(title)
        except Exception:
            pass

    def mouseDoubleClickEvent(self, event):
        # Double-click toggles maximize/restore
        self._on_maximize()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            w = self._resolve_window()
            # Try platform native move if supported
            try:
                wh = w.windowHandle() if w is not None else None
                if wh is not None and hasattr(wh, 'startSystemMove'):
                    wh.startSystemMove()
                    event.accept()
                    return
            except Exception:
                pass

            if w and not w.isMaximized():
                self._drag_pos = event.globalPosition().toPoint()
                event.accept()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is None:
            return super().mouseMoveEvent(event)
        w = self._resolve_window()
        if not w:
            return
        if event.buttons() & Qt.LeftButton:
            new_pos = event.globalPosition().toPoint()
            delta = new_pos - self._drag_pos
            self._drag_pos = new_pos
            w.move(w.pos() + delta)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        return super().mouseReleaseEvent(event)
