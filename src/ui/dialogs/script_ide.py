"""
Script IDE - Complete development environment for SCADA Scout scripts.
Features: code editor, debugger, variable inspector, console, file management.
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QToolBar, QStatusBar, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QLabel, QFileDialog, QMessageBox, QInputDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QMenuBar, QMenu,
    QDockWidget
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSettings
from PySide6.QtGui import QAction, QKeySequence, QFont, QColor, QIcon, QShortcut
import os
import json
import traceback
import threading
from pathlib import Path
from typing import Optional, Dict, Any

from src.ui.widgets.code_editor import CodeEditor
from src.core.script_debugger import ScriptDebugger, DebuggerThread
from src.core.script_runtime import ScriptContext


class ScriptIDEWindow(QMainWindow):
    """
    Complete IDE for writing and debugging SCADA Scout Python scripts.
    Similar to Triangle Microworks DTM Insight JS environment.
    """
    
    # Signals for thread-safe UI updates
    debugger_break_signal = Signal(str, int, dict)
    debugger_finish_signal = Signal(object)
    debugger_output_signal = Signal(str)
    
    def __init__(self, device_manager, event_logger=None, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.event_logger = event_logger
        
        self.setWindowTitle("SCADA Scout - Script IDE")
        self.resize(1400, 900)
        
        # Current script state
        self.current_file: Optional[Path] = None
        self.is_modified = False
        self.scripts_dir = Path("scripts")
        self.scripts_dir.mkdir(exist_ok=True)
        
        # Debugger
        self.debugger = ScriptDebugger()
        self.debugger.on_break = self._on_debugger_break
        self.debugger.on_finish = self._on_debugger_finish
        self.debugger.on_output = self._on_debugger_output
        self.debugger_thread: Optional[DebuggerThread] = None

        # Run loop state
        self.run_timer = QTimer(self)
        self.run_timer.setSingleShot(False)
        self.run_timer.timeout.connect(self._run_tick_once)
        self._run_ctx: Optional[ScriptContext] = None
        self._run_namespace: Optional[Dict[str, Any]] = None
        self._run_tick_func = None
        
        # Breakpoint tracking (line -> bp_id)
        self.line_to_bp_id: Dict[int, int] = {}

        # Settings
        self.settings = QSettings("ScadaScout", "ScriptIDE")
        
        # Thread synchronization for UI updates
        self._ui_update_lock = threading.Lock()
        self._ui_update_event = threading.Event()
        
        self._setup_ui()
        self._setup_menubar()
        self._setup_toolbar()
        self._connect_signals()

        # Load persisted run settings
        self._load_run_settings()
        
        # Load default template
        self._load_template()
        
        self.statusBar().showMessage("Ready")
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Central widget with main splitter
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main horizontal splitter: file browser | editor | inspector
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: File browser
        file_panel = self._create_file_browser()
        main_splitter.addWidget(file_panel)
        
        # Center panel: Editor with tabs
        editor_panel = self._create_editor_panel()
        main_splitter.addWidget(editor_panel)
        
        # Right panel: Variable inspector and stack trace
        inspector_panel = self._create_inspector_panel()
        main_splitter.addWidget(inspector_panel)
        
        # Set initial sizes
        main_splitter.setSizes([250, 800, 350])
        
        layout.addWidget(main_splitter)
        
        # Bottom panel: Console output
        bottom_dock = QDockWidget("Console Output", self)
        bottom_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 9))
        self.console.setMaximumHeight(200)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #3E3E3E;
            }
        """)
        bottom_dock.setWidget(self.console)
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom_dock)
    
    def _create_file_browser(self) -> QWidget:
        """Create file browser panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("Scripts"))
        
        # Tree widget for file navigation
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Files")
        self.file_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #252526;
                color: #CCCCCC;
                border: 1px solid #3E3E3E;
            }
        """)
        self.file_tree.itemDoubleClicked.connect(self._on_file_double_clicked)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._show_file_context_menu)
        # Enable keyboard shortcut for delete
        delete_shortcut = QShortcut(QKeySequence.Delete, self.file_tree)
        delete_shortcut.activated.connect(self._delete_selected_file)
        layout.addWidget(self.file_tree)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_new = QPushButton("New")
        btn_new.clicked.connect(self._new_script)
        btn_layout.addWidget(btn_new)
        
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_file_tree)
        btn_layout.addWidget(btn_refresh)
        
        layout.addLayout(btn_layout)
        
        # Initial population
        self._refresh_file_tree()
        
        return widget
    
    def _create_editor_panel(self) -> QWidget:
        """Create editor panel with tabs."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget for multiple files
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self._close_tab)
        
        # Main editor
        self.editor = CodeEditor()
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.breakpoint_toggled.connect(self._on_breakpoint_toggled)
        
        # Add F9 shortcut for toggling breakpoint at current line
        toggle_bp_shortcut = QShortcut(QKeySequence("F9"), self.editor)
        toggle_bp_shortcut.activated.connect(self._toggle_breakpoint_at_cursor)
        
        self.editor_tabs.addTab(self.editor, "untitled.py")
        
        layout.addWidget(self.editor_tabs)
        
        return widget
    
    def _create_inspector_panel(self) -> QWidget:
        """Create variable inspector and stack trace panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Tab widget for different views
        tabs = QTabWidget()
        
        # Variables tab
        self.var_table = QTableWidget()
        self.var_table.setColumnCount(2)
        self.var_table.setHorizontalHeaderLabels(["Variable", "Value"])
        self.var_table.horizontalHeader().setStretchLastSection(True)
        self.var_table.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #CCCCCC;
                border: 1px solid #3E3E3E;
            }
        """)
        tabs.addTab(self.var_table, "Variables")
        
        # Stack trace tab
        self.stack_tree = QTreeWidget()
        self.stack_tree.setHeaderLabel("Call Stack")
        self.stack_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #252526;
                color: #CCCCCC;
                border: 1px solid #3E3E3E;
            }
        """)
        tabs.addTab(self.stack_tree, "Stack")
        
        # Breakpoints tab
        self.bp_table = QTableWidget()
        self.bp_table.setColumnCount(3)
        self.bp_table.setHorizontalHeaderLabels(["File", "Line", "Enabled"])
        self.bp_table.horizontalHeader().setStretchLastSection(True)
        self.bp_table.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #CCCCCC;
                border: 1px solid #3E3E3E;
            }
        """)
        # Double-click to jump to breakpoint
        self.bp_table.cellDoubleClicked.connect(self._jump_to_breakpoint)
        # Delete key to remove breakpoint
        bp_delete_shortcut = QShortcut(QKeySequence.Delete, self.bp_table)
        bp_delete_shortcut.activated.connect(self._delete_selected_breakpoint)
        tabs.addTab(self.bp_table, "Breakpoints")
        
        # Watch expressions tab
        watch_widget = QWidget()
        watch_layout = QVBoxLayout(watch_widget)
        
        watch_input_layout = QHBoxLayout()
        self.watch_input = QLineEdit()
        self.watch_input.setPlaceholderText("Enter expression to watch...")
        watch_input_layout.addWidget(self.watch_input)
        
        btn_add_watch = QPushButton("Add")
        btn_add_watch.clicked.connect(self._add_watch)
        watch_input_layout.addWidget(btn_add_watch)
        
        watch_layout.addLayout(watch_input_layout)
        
        self.watch_table = QTableWidget()
        self.watch_table.setColumnCount(2)
        self.watch_table.setHorizontalHeaderLabels(["Expression", "Value"])
        self.watch_table.horizontalHeader().setStretchLastSection(True)
        self.watch_table.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #CCCCCC;
                border: 1px solid #3E3E3E;
            }
        """)
        watch_layout.addWidget(self.watch_table)
        
        tabs.addTab(watch_widget, "Watch")
        
        layout.addWidget(tabs)
        
        return widget
    
    def _setup_menubar(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Script", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._new_script)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self._save_file_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        close_action = QAction("Close", self)
        close_action.setShortcut(QKeySequence.Close)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self.editor.undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self.editor.redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        find_action = QAction("Find...", self)
        find_action.setShortcut(QKeySequence.Find)
        find_action.triggered.connect(self._show_find)
        edit_menu.addAction(find_action)
        
        # Debug menu
        debug_menu = menubar.addMenu("Debug")
        
        self.run_action = QAction("Run", self)
        self.run_action.setShortcut(QKeySequence("F5"))
        self.run_action.triggered.connect(self._run_script)
        debug_menu.addAction(self.run_action)
        
        self.debug_action = QAction("Debug", self)
        self.debug_action.setShortcut(QKeySequence("Shift+F9"))
        self.debug_action.triggered.connect(self._debug_script)
        debug_menu.addAction(self.debug_action)
        
        toggle_bp_action = QAction("Toggle Breakpoint", self)
        toggle_bp_action.setShortcut(QKeySequence("F9"))
        toggle_bp_action.triggered.connect(self._toggle_breakpoint_at_cursor)
        debug_menu.addAction(toggle_bp_action)
        
        clear_bp_action = QAction("Clear All Breakpoints", self)
        clear_bp_action.setShortcut(QKeySequence("Ctrl+Shift+F9"))
        clear_bp_action.triggered.connect(self._clear_all_breakpoints)
        debug_menu.addAction(clear_bp_action)
        
        self.stop_action = QAction("Stop", self)
        self.stop_action.setShortcut(QKeySequence("Shift+F5"))
        self.stop_action.triggered.connect(self._stop_execution)
        self.stop_action.setEnabled(False)
        debug_menu.addAction(self.stop_action)
        
        debug_menu.addSeparator()
        
        self.step_over_action = QAction("Step Over", self)
        self.step_over_action.setShortcut(QKeySequence("F10"))
        self.step_over_action.triggered.connect(self._step_over)
        self.step_over_action.setEnabled(False)
        debug_menu.addAction(self.step_over_action)
        
        self.step_into_action = QAction("Step Into", self)
        self.step_into_action.setShortcut(QKeySequence("F11"))
        self.step_into_action.triggered.connect(self._step_into)
        self.step_into_action.setEnabled(False)
        debug_menu.addAction(self.step_into_action)
        
        self.step_out_action = QAction("Step Out", self)
        self.step_out_action.setShortcut(QKeySequence("Shift+F11"))
        self.step_out_action.triggered.connect(self._step_out)
        self.step_out_action.setEnabled(False)
        debug_menu.addAction(self.step_out_action)
        
        self.continue_action = QAction("Continue", self)
        self.continue_action.setShortcut(QKeySequence("F8"))
        self.continue_action.triggered.connect(self._continue_execution)
        self.continue_action.setEnabled(False)
        debug_menu.addAction(self.continue_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        help_action = QAction("Documentation", self)
        help_action.triggered.connect(self._show_help)
        help_menu.addAction(help_action)
        
        examples_action = QAction("Load Examples", self)
        examples_action.triggered.connect(self._load_examples)
        help_menu.addAction(examples_action)
    
    def _setup_toolbar(self):
        """Setup toolbar with debug controls."""
        toolbar = QToolBar("Debug Controls")
        self.addToolBar(toolbar)
        
        # Run button
        self.btn_run = QPushButton("▶ Run")
        self.btn_run.clicked.connect(self._run_script)
        self.btn_run.setStyleSheet("QPushButton { background-color: #0E639C; color: white; padding: 5px 15px; }")
        toolbar.addWidget(self.btn_run)

        # Run mode controls
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Run Mode:"))
        self.run_mode_combo = QComboBox()
        self.run_mode_combo.addItems(["Once", "Continuous"])
        self.run_mode_combo.setMaximumWidth(140)
        toolbar.addWidget(self.run_mode_combo)

        toolbar.addWidget(QLabel("Cycle (ms):"))
        self.run_interval_input = QLineEdit("1000")
        self.run_interval_input.setMaximumWidth(80)
        self.run_interval_input.setToolTip("Tick interval in milliseconds")
        toolbar.addWidget(self.run_interval_input)
        
        # Debug button
        self.btn_debug = QPushButton("🐞 Debug (Shift+F9)")
        self.btn_debug.clicked.connect(self._debug_script)
        self.btn_debug.setStyleSheet("QPushButton { background-color: #16825D; color: white; padding: 5px 15px; }")
        toolbar.addWidget(self.btn_debug)
        
        toolbar.addSeparator()
        
        # Toggle breakpoint button
        self.btn_toggle_bp = QPushButton("🔴 Toggle BP (F9)")
        self.btn_toggle_bp.clicked.connect(self._toggle_breakpoint_at_cursor)
        self.btn_toggle_bp.setStyleSheet("QPushButton { background-color: #5C2D91; color: white; padding: 5px 15px; }")
        toolbar.addWidget(self.btn_toggle_bp)
        
        self.btn_clear_bp = QPushButton("Clear All BP")
        self.btn_clear_bp.clicked.connect(self._clear_all_breakpoints)
        toolbar.addWidget(self.btn_clear_bp)
        
        # Stop button
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.clicked.connect(self._stop_execution)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("QPushButton { background-color: #A1260D; color: white; padding: 5px 15px; }")
        toolbar.addWidget(self.btn_stop)
        
        toolbar.addSeparator()
        
        # Step controls
        self.btn_step_over = QPushButton("⤵ Step Over (F10)")
        self.btn_step_over.clicked.connect(self._step_over)
        self.btn_step_over.setEnabled(False)
        toolbar.addWidget(self.btn_step_over)
        
        self.btn_step_into = QPushButton("⤴ Step Into (F11)")
        self.btn_step_into.clicked.connect(self._step_into)
        self.btn_step_into.setEnabled(False)
        toolbar.addWidget(self.btn_step_into)
        
        self.btn_step_out = QPushButton("⤴ Step Out (Shift+F11)")
        self.btn_step_out.clicked.connect(self._step_out)
        self.btn_step_out.setEnabled(False)
        toolbar.addWidget(self.btn_step_out)
        
        self.btn_continue = QPushButton("▶▶ Continue (F8)")
        self.btn_continue.clicked.connect(self._continue_execution)
        self.btn_continue.setEnabled(False)
        toolbar.addWidget(self.btn_continue)
    
    def _connect_signals(self):
        """Connect internal signals."""
        # Connect debugger signals to UI update slots
        self.debugger_break_signal.connect(self._update_debug_ui)
        self.debugger_finish_signal.connect(self._finish_debug)
        self.debugger_output_signal.connect(self.console.append)

        # Persist run settings when changed
        if hasattr(self, "run_mode_combo"):
            self.run_mode_combo.currentIndexChanged.connect(self._save_run_settings)
        if hasattr(self, "run_interval_input"):
            self.run_interval_input.editingFinished.connect(self._save_run_settings)

    def _load_run_settings(self):
        """Load persisted run settings."""
        try:
            mode = self.settings.value("run_mode", "Once")
            interval = self.settings.value("run_interval_ms", "1000")
            if hasattr(self, "run_mode_combo"):
                index = self.run_mode_combo.findText(str(mode))
                if index >= 0:
                    self.run_mode_combo.setCurrentIndex(index)
            if hasattr(self, "run_interval_input"):
                self.run_interval_input.setText(str(interval))
        except Exception:
            pass

    def _save_run_settings(self):
        """Save run settings."""
        try:
            if hasattr(self, "run_mode_combo"):
                self.settings.setValue("run_mode", self.run_mode_combo.currentText())
            if hasattr(self, "run_interval_input"):
                self.settings.setValue("run_interval_ms", self.run_interval_input.text().strip())
        except Exception:
            pass
    
    def _refresh_file_tree(self):
        """Refresh the file browser tree."""
        self.file_tree.clear()
        
        if not self.scripts_dir.exists():
            return
        
        for file_path in sorted(self.scripts_dir.glob("*.py")):
            item = QTreeWidgetItem([file_path.name])
            # Use absolute path for consistency
            item.setData(0, Qt.UserRole, str(file_path.resolve()))
            self.file_tree.addTopLevelItem(item)
    
    def _show_file_context_menu(self, position):
        """Show context menu for file browser."""
        item = self.file_tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._on_file_double_clicked(item, 0))
        
        menu.addSeparator()
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self._delete_selected_file)
        
        menu.exec_(self.file_tree.viewport().mapToGlobal(position))
    
    def _delete_selected_file(self):
        """Delete the selected file from disk."""
        item = self.file_tree.currentItem()
        if not item:
            return
        
        file_path_str = item.data(0, Qt.UserRole)
        if not file_path_str:
            return
        
        file_path = Path(file_path_str)
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Delete Script",
            f"Are you sure you want to delete '{file_path.name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Close tab if file is currently open
                if self.current_file and self.current_file.resolve() == file_path.resolve():
                    # If it's the current file, reset to new
                    self.current_file = None
                    self.is_modified = False
                    self._load_template()
                    self.editor_tabs.setTabText(0, "untitled.py")
                    self._update_title()
                
                # Delete the file
                file_path.unlink()
                
                # Refresh file tree
                self._refresh_file_tree()
                
                self.console.append(f"<span style='color: #CE9178;'>Deleted: {file_path.name}</span>")
                
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error",
                    f"Failed to delete file:\n{e}"
                )
    
    def _on_file_double_clicked(self, item, column):
        """Handle double-click on file."""
        file_path = item.data(0, Qt.UserRole)
        if file_path:
            self._load_file(Path(file_path))
    
    def _new_script(self):
        """Create a new script."""
        if self._check_unsaved_changes():
            self.current_file = None
            self.editor.clear()
            self._load_template()
            self.editor_tabs.setTabText(0, "untitled.py")
            self.is_modified = False
            self._update_title()
    
    def _open_file(self):
        """Open a script file."""
        if not self._check_unsaved_changes():
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Script", str(self.scripts_dir), "Python Files (*.py);;All Files (*)"
        )
        
        if file_path:
            self._load_file(Path(file_path))
    
    def _load_file(self, file_path: Path):
        """Load a script from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.editor.setPlainText(content)
            self.current_file = file_path
            self.editor_tabs.setTabText(0, file_path.name)
            self.is_modified = False
            self._update_title()
            self.console.append(f"<span style='color: #4EC9B0;'>Loaded: {file_path}</span>")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")
    
    def _save_file(self):
        """Save the current script."""
        if self.current_file:
            self._save_to_file(self.current_file)
        else:
            self._save_file_as()
    
    def _save_file_as(self):
        """Save the current script with a new name."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Script", str(self.scripts_dir / "untitled.py"), 
            "Python Files (*.py);;All Files (*)"
        )
        
        if file_path:
            self._save_to_file(Path(file_path))
    
    def _save_to_file(self, file_path: Path):
        """Save content to file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            
            self.current_file = file_path
            self.editor_tabs.setTabText(0, file_path.name)
            self.is_modified = False
            self._update_title()
            self._refresh_file_tree()
            self.console.append(f"<span style='color: #4EC9B0;'>Saved: {file_path}</span>")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")
    
    def _close_tab(self, index):
        """Close a tab."""
        if self._check_unsaved_changes():
            self.editor_tabs.removeTab(index)
            # If no tabs remain, reset to new script state
            if self.editor_tabs.count() == 0:
                self.current_file = None
                self.is_modified = False
                self._load_template()
                self.editor_tabs.addTab(self.editor, "untitled.py")
                self._update_title()
    
    def _check_unsaved_changes(self) -> bool:
        """Check for unsaved changes and prompt user."""
        if self.is_modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Do you want to save your changes?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self._save_file()
                return True
            elif reply == QMessageBox.Discard:
                return True
            else:
                return False
        return True
    
    def _on_text_changed(self):
        """Handle text changes."""
        self.is_modified = True
        self._update_title()
    
    def _update_title(self):
        """Update window title."""
        filename = self.current_file.name if self.current_file else "untitled.py"
        modified = "*" if self.is_modified else ""
        self.setWindowTitle(f"SCADA Scout - Script IDE - {filename}{modified}")
    
    def _load_template(self):
        """Load default script template."""
        template = '''"""
SCADA Scout Script
Write your automation logic here.
"""

def tick(ctx):
    """
    Called repeatedly at configured interval.
    
    Available methods:
    - ctx.get(tag_address, default=None)  # Get cached value
    - ctx.read(tag_address)  # Force read
    - ctx.set(tag_address, value)  # Write value
    - ctx.send_command(tag_address, value, params=None)  # IEC 61850 control
    - ctx.list_tags(device_name=None)  # List available tags
    - ctx.log(level, message)  # Log message
    
    Tag format: DeviceName::SignalAddress
    Examples:
      - IED1::LD/CSWI1.Pos.stVal
      - Modbus::1:3:40001
    """
    # Your code here
    pass


def main(ctx):
    """
    Called once when script is run.
    Use this for one-time operations.
    """
    ctx.log('info', 'Script started')
'''
        self.editor.setPlainText(template)
    
    def _toggle_breakpoint_at_cursor(self):
        """Toggle breakpoint at the current cursor line."""
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1  # Lines are 1-indexed
        self.editor.toggle_breakpoint_at_line(line)
    
    def _on_breakpoint_toggled(self, line: int, is_set: bool):
        """Handle breakpoint toggle in editor."""
        if is_set:
            # Add breakpoint to debugger
            # Use resolved absolute path
            filename = str(self.current_file.resolve()) if self.current_file else '<script>'
            bp_id = self.debugger.add_breakpoint(filename, line)
            self.line_to_bp_id[line] = bp_id
        else:
            # Remove breakpoint from debugger
            if line in self.line_to_bp_id:
                bp_id = self.line_to_bp_id[line]
                self.debugger.remove_breakpoint(bp_id)
                del self.line_to_bp_id[line]
        
        self._update_breakpoint_list()
    
    def _update_breakpoint_list(self):
        """Update breakpoint table."""
        self.bp_table.setRowCount(0)
        
        for bp_id, bp in self.debugger.breakpoints.items():
            row = self.bp_table.rowCount()
            self.bp_table.insertRow(row)
            
            file_item = QTableWidgetItem(bp.file)
            file_item.setData(Qt.UserRole, bp_id)  # Store bp_id for later use
            self.bp_table.setItem(row, 0, file_item)
            self.bp_table.setItem(row, 1, QTableWidgetItem(str(bp.line)))
            self.bp_table.setItem(row, 2, QTableWidgetItem("Yes" if bp.enabled else "No"))
    
    def _jump_to_breakpoint(self, row, column):
        """Jump to the breakpoint in the editor."""
        line_item = self.bp_table.item(row, 1)
        if line_item:
            line = int(line_item.text())
            # Move cursor to that line
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.Start)
            for _ in range(line - 1):
                cursor.movePosition(cursor.Down)
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()
            self.editor.setFocus()
    
    def _delete_selected_breakpoint(self):
        """Delete the selected breakpoint from the list."""
        current_row = self.bp_table.currentRow()
        if current_row < 0:
            return
        
        file_item = self.bp_table.item(current_row, 0)
        line_item = self.bp_table.item(current_row, 1)
        if not file_item or not line_item:
            return
        
        bp_id = file_item.data(Qt.UserRole)
        line = int(line_item.text())
        
        # Remove from debugger
        if bp_id and self.debugger.remove_breakpoint(bp_id):
            # Remove from editor visual
            if line in self.editor.breakpoints:
                self.editor.breakpoints.remove(line)
                self.editor.line_number_area.update()
            # Remove from tracking
            if line in self.line_to_bp_id:
                del self.line_to_bp_id[line]
            # Update list
            self._update_breakpoint_list()
    
    def _clear_all_breakpoints(self):
        """Clear all breakpoints."""
        # Clear from debugger
        self.debugger.clear_all_breakpoints()
        # Clear from editor
        self.editor.clear_breakpoints()
        # Clear tracking
        self.line_to_bp_id.clear()
        # Update list
        self._update_breakpoint_list()
        self.console.append("<span style='color: #CE9178;'>All breakpoints cleared</span>")
    
    def _run_script(self):
        """Run script without debugging."""
        if self.debugger.is_running:
            QMessageBox.warning(self, "Already Running", "A script is currently being debugged.")
            return
        if self.run_timer.isActive():
            QMessageBox.warning(self, "Already Running", "Continuous run is already active.")
            return

        code = self.editor.toPlainText()
        
        self.console.clear()
        self.console.append("<span style='color: #4EC9B0;'>▶ Running script...</span>")
        
        # Create script context
        from src.core.device_manager_core import DeviceManagerCore
        dm_core = getattr(self.device_manager, '_core', None)
        if not dm_core:
            self.console.append("<span style='color: #E51400;'>Error: Device manager not available</span>")
            return
        
        ctx = ScriptContext(dm_core, self.event_logger)
        run_mode = self.run_mode_combo.currentText()
        interval_ms = self._get_run_interval_ms()

        try:
            # Execute script
            namespace = {'ctx': ctx}
            if self.current_file:
                namespace['__file__'] = str(self.current_file)
                
            exec(compile(code, '<script>', 'exec'), namespace)

            # Call entry point if defined
            if 'main' in namespace and callable(namespace['main']):
                namespace['main'](ctx)

            if run_mode == "Once":
                if 'tick' in namespace and callable(namespace['tick']):
                    namespace['tick'](ctx)
                self.console.append("<span style='color: #4EC9B0;'>✓ Script completed successfully</span>")
            else:
                # Continuous mode requires tick
                if 'tick' not in namespace or not callable(namespace['tick']):
                    self.console.append("<span style='color: #E51400;'>Error: Continuous mode requires a tick(ctx) function</span>")
                    return

                self._run_ctx = ctx
                self._run_namespace = namespace
                self._run_tick_func = namespace['tick']
                self.run_timer.start(interval_ms)
                self._set_debug_mode(True)
                self.console.append(
                    f"<span style='color: #4EC9B0;'>▶ Continuous run started (cycle={interval_ms} ms)</span>"
                )
            
        except Exception as e:
            self.console.append(f"<span style='color: #E51400;'>✗ Error: {e}</span>")
            self.console.append(f"<pre>{traceback.format_exc()}</pre>")
    
    def _debug_script(self):
        """Start debugging the script."""
        if self.debugger.is_running:
            QMessageBox.warning(self, "Already Running", "A script is already being debugged.")
            return
        
        code = self.editor.toPlainText()
        # Ensure we use the resolved absolute path
        filename = str(self.current_file.resolve()) if self.current_file else '<script>'
        
        self.console.clear()
        self.console.append("<span style='color: #DCDCAA;'>🐞 Starting debugger...</span>")
        
        # Create script context
        from src.core.device_manager_core import DeviceManagerCore
        dm_core = getattr(self.device_manager, '_core', None)
        if not dm_core:
            self.console.append("<span style='color: #E51400;'>Error: Device manager not available</span>")
            return
        
        ctx = ScriptContext(dm_core, self.event_logger)
        namespace = {'ctx': ctx}
        if self.current_file:
            namespace['__file__'] = str(self.current_file)
        
        # Start debugger thread
        self.debugger_thread = DebuggerThread(self.debugger, code, namespace, filename)
        self.debugger_thread.start()
        
        # Update UI
        self._set_debug_mode(True)
    
    def _stop_execution(self):
        """Stop script execution."""
        if self.run_timer.isActive():
            self.run_timer.stop()
            self._run_ctx = None
            self._run_namespace = None
            self._run_tick_func = None
            self._set_debug_mode(False)
            self.console.append("<span style='color: #A1260D;'>⏹ Continuous run stopped</span>")
            return

        if self.debugger.is_running:
            self.debugger.do_stop()
            self.console.append("<span style='color: #A1260D;'>⏹ Stopped</span>")
            # Clear execution line highlight
            self.editor.clear_current_execution_line()
            # Reset UI immediately
            self._set_debug_mode(False)
            self._set_step_controls(False)

    def _get_run_interval_ms(self) -> int:
        """Get run interval from UI, fallback to 1000ms."""
        try:
            value = int(self.run_interval_input.text().strip())
            return max(10, value)
        except Exception:
            return 1000

    def _run_tick_once(self):
        """Execute one tick cycle for continuous run."""
        if not self._run_tick_func or not self._run_ctx:
            return
        try:
            self._run_tick_func(self._run_ctx)
        except Exception as e:
            self.console.append(f"<span style='color: #E51400;'>✗ Tick error: {e}</span>")
            self.console.append(f"<pre>{traceback.format_exc()}</pre>")
            self._stop_execution()
    
    def _step_over(self):
        """Step over next line."""
        if self.debugger.is_paused:
            self.debugger.do_step_over()
    
    def _step_into(self):
        """Step into function."""
        if self.debugger.is_paused:
            self.debugger.do_step_into()
    
    def _step_out(self):
        """Step out of function."""
        if self.debugger.is_paused:
            self.debugger.do_step_out()
    
    def _continue_execution(self):
        """Continue execution."""
        if self.debugger.is_paused:
            self.debugger.do_continue()
            self.editor.clear_current_execution_line()
    
    def _on_debugger_break(self, filename: str, line: int, locals_dict: Dict[str, Any]):
        """Called when debugger breaks at a line (from debugger thread)."""
        # Emit signal to update UI on main thread and wait for UI to finish
        self._ui_update_event.clear()
        self.debugger_break_signal.emit(filename, line, locals_dict)
        # Wait for UI update to complete (with timeout to prevent deadlock)
        self._ui_update_event.wait(timeout=5.0)
    
    def _update_debug_ui(self, filename: str, line: int, locals_dict: Dict[str, Any]):
        """Update UI when debugger pauses (runs on main thread)."""
        try:
            # Highlight current line
            self.editor.set_current_execution_line(line)
            
            # Update variables table
            self.var_table.setRowCount(0)
            for name, value in sorted(locals_dict.items()):
                if not name.startswith('__'):
                    row = self.var_table.rowCount()
                    self.var_table.insertRow(row)
                    self.var_table.setItem(row, 0, QTableWidgetItem(name))
                    self.var_table.setItem(row, 1, QTableWidgetItem(str(value)))
            
            # Update stack trace
            self.stack_tree.clear()
            for frame in self.debugger.get_stack_trace():
                item = QTreeWidgetItem([
                    f"{frame.function} at {frame.file}:{frame.line}"
                ])
                self.stack_tree.addTopLevelItem(item)
            
            # Update watch expressions
            self._update_watch_expressions()
            
            self.console.append(f"<span style='color: #DCDCAA;'>⏸ Paused at line {line}</span>")
            
            # Enable step controls
            self._set_step_controls(True)
        finally:
            # Signal that UI update is complete
            self._ui_update_event.set()
    
    def _on_debugger_finish(self, exception: Optional[Exception]):
        """Called when debugger finishes (from debugger thread)."""
        self.debugger_finish_signal.emit(exception)
    
    def _finish_debug(self, exception: Optional[Exception]):
        """Finish debugging session."""
        self.editor.clear_current_execution_line()
        self._set_debug_mode(False)
        
        if exception:
            self.console.append(f"<span style='color: #E51400;'>✗ Exception: {exception}</span>")
        else:
            self.console.append("<span style='color: #4EC9B0;'>✓ Debug session completed</span>")
    
    def _on_debugger_output(self, text: str):
        """Handle debugger output (from debugger thread)."""
        self.debugger_output_signal.emit(text)
    
    def _set_debug_mode(self, enabled: bool):
        """Enable/disable debug mode UI."""
        self.btn_run.setEnabled(not enabled)
        self.btn_debug.setEnabled(not enabled)
        self.btn_stop.setEnabled(enabled)
        
        self.run_action.setEnabled(not enabled)
        self.debug_action.setEnabled(not enabled)
        self.stop_action.setEnabled(enabled)
    
    def _set_step_controls(self, enabled: bool):
        """Enable/disable step controls."""
        self.btn_step_over.setEnabled(enabled)
        self.btn_step_into.setEnabled(enabled)
        self.btn_step_out.setEnabled(enabled)
        self.btn_continue.setEnabled(enabled)
        
        self.step_over_action.setEnabled(enabled)
        self.step_into_action.setEnabled(enabled)
        self.step_out_action.setEnabled(enabled)
        self.continue_action.setEnabled(enabled)
    
    def _add_watch(self):
        """Add a watch expression."""
        expr = self.watch_input.text().strip()
        if expr:
            row = self.watch_table.rowCount()
            self.watch_table.insertRow(row)
            self.watch_table.setItem(row, 0, QTableWidgetItem(expr))
            self.watch_table.setItem(row, 1, QTableWidgetItem(""))
            self.watch_input.clear()
            
            self._update_watch_expressions()
    
    def _update_watch_expressions(self):
        """Update all watch expression values."""
        for row in range(self.watch_table.rowCount()):
            expr = self.watch_table.item(row, 0).text()
            value = self.debugger.evaluate_expression(expr)
            self.watch_table.setItem(row, 1, QTableWidgetItem(value))
    
    def _show_find(self):
        """Show find dialog."""
        # TODO: Implement find dialog
        pass
    
    def _show_help(self):
        """Show help documentation."""
        help_text = """
<h2>SCADA Scout Script IDE</h2>

<h3>Quick Start</h3>
<ul>
<li><b>F5</b> - Run script without debugging</li>
<li><b>F9</b> - Start debugging</li>
<li><b>F10</b> - Step over</li>
<li><b>F11</b> - Step into</li>
<li><b>Shift+F11</b> - Step out</li>
<li><b>F8</b> - Continue</li>
<li><b>Shift+F5</b> - Stop</li>
</ul>

<h3>Breakpoints</h3>
<p>Click in the line number area to toggle breakpoints (red circles).</p>

<h3>Script Context API</h3>
<pre>
ctx.get(tag_address, default=None)  # Get cached value
ctx.read(tag_address)  # Force read from device
ctx.set(tag_address, value)  # Write to device
ctx.send_command(tag, value, params=None)  # IEC 61850 control
ctx.list_tags(device_name=None)  # List available tags
ctx.log(level, message)  # Log message
</pre>

<h3>Tag Address Format</h3>
<p><code>DeviceName::SignalAddress</code></p>
<ul>
<li>IEC 61850: <code>IED1::LD/CSWI1.Pos.stVal</code></li>
<li>Modbus: <code>Device::1:3:40001</code></li>
</ul>
        """
        
        QMessageBox.information(self, "Help", help_text)
    
    def _load_examples(self):
        """Load example scripts."""
        # TODO: Provide example scripts
        examples = [
            ("Read and Write", "def tick(ctx):\n    val = ctx.get('Device::Address', 0)\n    ctx.set('Device::Output', val * 2)"),
            ("IEC 61850 Control", "def main(ctx):\n    ctx.send_command('IED::CB1.Pos', True)\n    ctx.log('info', 'Breaker closed')"),
        ]
        
        choice, ok = QInputDialog.getItem(
            self, "Load Example", "Select an example:", 
            [e[0] for e in examples], 0, False
        )
        
        if ok:
            for name, code in examples:
                if name == choice:
                    self.editor.setPlainText(code)
                    break
    
    def closeEvent(self, event):
        """Handle window close."""
        if self._check_unsaved_changes():
            # Stop debugger if running
            if self.debugger.is_running:
                self.debugger.do_stop()
            self._save_run_settings()
            event.accept()
        else:
            event.ignore()
