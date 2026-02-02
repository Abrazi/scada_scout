from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QListWidget, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import Qt
import textwrap


class IEC61131ScriptDialog(QDialog):
    """Simple editor/runner for IEC 61131 scripts."""
    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.setWindowTitle("IEC 61131 Scripts")
        self.resize(900, 600)
        self.setWindowModality(Qt.NonModal)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Script Name:"))
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g., PumpController")
        header.addWidget(self.txt_name)

        header.addWidget(QLabel("Interval (s):"))
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(0.05, 60.0)
        self.spin_interval.setSingleStep(0.05)
        self.spin_interval.setValue(0.5)
        header.addWidget(self.spin_interval)
        layout.addLayout(header)

        body = QHBoxLayout()
        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            "(* IEC 61131-3 Structured Text *)\n"
            "VAR\n"
            "    x : INT := 0;\n"
            "END_VAR\n\n"
            "x := x + 1;\n"
        )

        EXAMPLE = textwrap.dedent(
            """\
            (* IEC 61131-3 Structured Text example *)
            VAR
                counter : INT := 0;
            END_VAR

            counter := counter + 1;
            """
        ).strip()
        if not self.editor.toPlainText().strip():
            self.editor.setPlainText(EXAMPLE)
        body.addWidget(self.editor, 3)

        right = QVBoxLayout()
        right.addWidget(QLabel("Running IEC 61131 Scripts"))
        self.lst_running = QListWidget()
        right.addWidget(self.lst_running, 1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh_running)
        right.addWidget(self.btn_refresh)

        right.addWidget(QLabel("Saved IEC 61131 Scripts"))
        self.lst_saved = QListWidget()
        right.addWidget(self.lst_saved, 1)
        self.btn_load = QPushButton("Load")
        self.btn_load.clicked.connect(self._load_selected_saved)
        right.addWidget(self.btn_load)
        self.btn_save = QPushButton("Save Current")
        self.btn_save.clicked.connect(self._save_current)
        right.addWidget(self.btn_save)

        body.addLayout(right, 1)
        layout.addLayout(body)

        actions = QHBoxLayout()
        self.btn_run_once = QPushButton("Run Once")
        self.btn_run_once.clicked.connect(self._run_once)
        actions.addWidget(self.btn_run_once)

        self.btn_start = QPushButton("Start Continuous")
        self.btn_start.clicked.connect(self._start_continuous)
        actions.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop Selected")
        self.btn_stop.clicked.connect(self._stop_selected)
        actions.addWidget(self.btn_stop)

        actions.addStretch(1)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        actions.addWidget(self.btn_close)
        layout.addLayout(actions)

        self._refresh_running()
        self._refresh_saved()

    def _get_code(self) -> str:
        return self.editor.toPlainText().strip()

    def _get_name(self) -> str:
        return self.txt_name.text().strip()

    def _run_once(self):
        code = self._get_code()
        name = self._get_name() or "IEC61131_Script"
        if not code:
            QMessageBox.warning(self, "Missing Code", "Paste a script first.")
            return
        try:
            self.device_manager.run_iec61131_script_once(name, code)
        except Exception as exc:
            QMessageBox.critical(self, "Script Error", str(exc))

    def _start_continuous(self):
        code = self._get_code()
        name = self._get_name()
        if not code:
            QMessageBox.warning(self, "Missing Code", "Paste a script first.")
            return
        if not name:
            QMessageBox.warning(self, "Missing Name", "Provide a script name.")
            return
        interval = float(self.spin_interval.value())
        try:
            self.device_manager.save_iec61131_script(name, code, interval)
            self.device_manager.start_iec61131_script(name, code, interval)
            self._refresh_running()
        except Exception as exc:
            QMessageBox.critical(self, "Script Error", str(exc))

    def _stop_selected(self):
        item = self.lst_running.currentItem()
        if not item:
            return
        name = item.text()
        try:
            self.device_manager.stop_iec61131_script(name)
            self._refresh_running()
        except Exception as exc:
            QMessageBox.critical(self, "Stop Error", str(exc))

    def _save_current(self):
        name = self._get_name()
        code = self._get_code()
        interval = float(self.spin_interval.value())
        if not name:
            QMessageBox.warning(self, "Missing Name", "Provide a script name before saving.")
            return
        try:
            self.device_manager.save_iec61131_script(name, code, interval)
            self._refresh_saved()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def _load_selected_saved(self):
        item = self.lst_saved.currentItem()
        if not item:
            return
        name = item.text()
        try:
            scripts = self.device_manager.get_saved_iec61131_scripts()
            meta = scripts.get(name)
            if not meta:
                return
            code = meta.get('code', '')
            interval = meta.get('interval', 0.5)
            self.editor.setPlainText(code)
            self.spin_interval.setValue(interval)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    def _refresh_running(self):
        try:
            self.lst_running.clear()
            for name in self.device_manager.list_iec61131_scripts():
                self.lst_running.addItem(name)
        except Exception:
            pass

    def _refresh_saved(self):
        try:
            self.lst_saved.clear()
            scripts = self.device_manager.get_saved_iec61131_scripts()
            for name in sorted(scripts.keys()):
                self.lst_saved.addItem(name)
        except Exception:
            pass
