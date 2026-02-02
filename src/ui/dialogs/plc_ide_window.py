"""PLC IDE Window - Professional IEC 61131-3 development environment."""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QToolBar, QStatusBar, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QLabel, QMessageBox, QInputDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QMenuBar, QMenu,
    QDockWidget, QPlainTextEdit, QListWidget, QCheckBox, QSpinBox,
    QDialog, QFormLayout, QDialogButtonBox, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer, Signal, QRect, QSize
from PySide6.QtGui import (
    QAction, QKeySequence, QFont, QColor, QSyntaxHighlighter, QTextCharFormat,
    QTextFormat, QPainter, QTextCursor
)
import json
import logging
from typing import Optional
from pathlib import Path

from src.models.plc_models import (
    PLCDeviceExtension, PLCProgram, PLCTask, PLCMode, 
    IEC61131Language, TaskType, PLCVariable, PLCDataType,
    Breakpoint, DebugState, WatchExpression
)
from src.core.st_compiler import STCompiler
from src.core.plc_runtime import PLCRuntime

logger = logging.getLogger(__name__)


class STSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Structured Text."""
    
    def __init__(self, document):
        super().__init__(document)
        
        # Define formats
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor(86, 156, 214))  # Blue
        self.keyword_format.setFontWeight(QFont.Bold)
        
        self.type_format = QTextCharFormat()
        self.type_format.setForeground(QColor(78, 201, 176))  # Teal
        
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor(106, 153, 85))  # Green
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor(181, 206, 168))  # Light green
        
        # Keywords
        self.keywords = [
            'PROGRAM', 'END_PROGRAM', 'VAR', 'END_VAR', 'VAR_INPUT', 'VAR_OUTPUT',
            'VAR_IN_OUT', 'IF', 'THEN', 'ELSE', 'ELSIF', 'END_IF', 'CASE', 'OF',
            'END_CASE', 'FOR', 'TO', 'BY', 'DO', 'END_FOR', 'WHILE', 'END_WHILE',
            'REPEAT', 'UNTIL', 'END_REPEAT', 'FUNCTION', 'END_FUNCTION',
            'FUNCTION_BLOCK', 'END_FUNCTION_BLOCK', 'RETURN', 'EXIT',
            'TRUE', 'FALSE', 'AND', 'OR', 'NOT', 'XOR', 'MOD', 'DIV'
        ]
        
        # Data types
        self.types = [
            'BOOL', 'BYTE', 'WORD', 'DWORD', 'LWORD',
            'SINT', 'INT', 'DINT', 'LINT',
            'USINT', 'UINT', 'UDINT', 'ULINT',
            'REAL', 'LREAL', 'TIME', 'DATE', 'STRING'
        ]
    
    def highlightBlock(self, text):
        # Highlight keywords
        for keyword in self.keywords:
            pattern = r'\b' + keyword + r'\b'
            import re
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), self.keyword_format)
        
        # Highlight types
        for type_name in self.types:
            pattern = r'\b' + type_name + r'\b'
            import re
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self.setFormat(match.start(), match.end() - match.start(), self.type_format)
        
        # Highlight comments
        comment_start = text.find('(*')
        if comment_start >= 0:
            comment_end = text.find('*)', comment_start)
            if comment_end >= 0:
                self.setFormat(comment_start, comment_end - comment_start + 2, self.comment_format)
            else:
                self.setFormat(comment_start, len(text) - comment_start, self.comment_format)
        
        line_comment = text.find('//')
        if line_comment >= 0:
            self.setFormat(line_comment, len(text) - line_comment, self.comment_format)
        
        # Highlight numbers
        import re
        for match in re.finditer(r'\b\d+\.?\d*\b', text):
            self.setFormat(match.start(), match.end() - match.start(), self.number_format)


class CodeEditor(QPlainTextEdit):
    """Code editor with breakpoint gutter and line numbers."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.breakpoints = set()  # Set of line numbers
        self.current_debug_line: Optional[int] = None
        
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        
        self.update_line_number_area_width(0)
    
    def line_number_area_width(self) -> int:
        """Calculate width needed for line number area."""
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits + 30  # Extra for breakpoints
        return space
    
    def update_line_number_area_width(self, _):
        """Update margins for line number area."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """Update line number area on scroll."""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
    
    def line_number_area_paint_event(self, event):
        """Paint line numbers and breakpoints."""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(30, 30, 30))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line_number = block_number + 1
                
                # Draw breakpoint indicator
                if line_number in self.breakpoints:
                    painter.setBrush(QColor(200, 50, 50))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(5, int(top) + 2, 12, 12)
                
                # Draw current debug line indicator
                if line_number == self.current_debug_line:
                    painter.fillRect(QRect(0, int(top), self.line_number_area.width(), 
                                          self.fontMetrics().height()), QColor(255, 255, 0, 40))
                
                # Draw line number
                painter.setPen(QColor(128, 128, 128))
                painter.drawText(0, int(top), self.line_number_area.width() - 5, 
                               self.fontMetrics().height(), Qt.AlignRight, str(line_number))
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    
    def toggle_breakpoint(self, line: int):
        """Toggle breakpoint at line."""
        if line in self.breakpoints:
            self.breakpoints.remove(line)
        else:
            self.breakpoints.add(line)
        self.line_number_area.update()
    
    def get_line_at_cursor(self) -> int:
        """Get line number at cursor."""
        return self.textCursor().blockNumber() + 1
    
    def mousePressEvent(self, event):
        """Handle mouse press for breakpoint toggle."""
        # Check if click is in gutter area
        if event.x() < self.line_number_area_width():
            # Get line number at click position
            cursor = self.cursorForPosition(event.pos())
            line_number = cursor.blockNumber() + 1
            self.toggle_breakpoint(line_number)
        else:
            super().mousePressEvent(event)


class LineNumberArea(QWidget):
    """Line number and breakpoint gutter widget."""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor
    
    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class PLCIDEWindow(QMainWindow):
    """Professional PLC IDE for IEC 61131-3 development."""
    
    def __init__(self, device_manager, device_name: str, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.device_name = device_name
        
        # Get device
        self.device = device_manager.get_device(device_name)
        if not self.device:
            raise ValueError(f"Device {device_name} not found")
        
        # Initialize or get PLC extension
        if not hasattr(self.device, 'plc_extension'):
            self.device.plc_extension = PLCDeviceExtension()
        self.plc_ext = self.device.plc_extension
        
        # Initialize compiler and runtime
        self.compiler = STCompiler()
        # Use PLC IDE's own logging method instead of main event logger
        self.runtime = PLCRuntime(self.plc_ext, self._plc_log)
        
        self.current_program: Optional[PLCProgram] = None
        
        self.setWindowTitle(f"PLC IDE - {device_name}")
        self.resize(1400, 900)
        
        self._setup_ui()
        self._setup_menubar()
        self._setup_toolbar()
        
        # Refresh timer for runtime status
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(500)  # 2Hz
        
        self.statusBar().showMessage("Ready")
    
    def _setup_ui(self):
        """Setup user interface with debugging panels."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Program/Task tree with controls
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Task configuration button
        btn_task_config = QPushButton("⚙️ Task Settings")
        btn_task_config.clicked.connect(self._configure_tasks)
        left_layout.addWidget(btn_task_config)
        
        # Project tree
        left_panel = self._create_project_tree()
        left_layout.addWidget(left_panel)
        
        main_splitter.addWidget(left_widget)
        
        # Center: Code editor
        editor_panel = self._create_editor_panel()
        main_splitter.addWidget(editor_panel)
        
        # Right: Variable inspector + debugging panels
        right_tabs = QTabWidget()
        right_tabs.addTab(self._create_variable_panel(), "Variables")
        right_tabs.addTab(self._create_watch_panel(), "Watch")
        right_tabs.addTab(self._create_callstack_panel(), "Call Stack")
        main_splitter.addWidget(right_tabs)
        
        main_splitter.setSizes([250, 800, 350])
        layout.addWidget(main_splitter)
        
        # Bottom: Output console
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        self.output_console.setMaximumHeight(150)
        self.output_console.setFont(QFont("Consolas", 9))
        layout.addWidget(self.output_console)
    
    def _create_project_tree(self) -> QWidget:
        """Create project tree widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("Programs & Tasks"))
        
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabel("Project")
        self.project_tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        layout.addWidget(self.project_tree)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_new_program = QPushButton("New Program")
        btn_new_program.clicked.connect(self._new_program)
        btn_layout.addWidget(btn_new_program)
        
        btn_new_task = QPushButton("New Task")
        btn_new_task.clicked.connect(self._new_task)
        btn_layout.addWidget(btn_new_task)
        
        layout.addLayout(btn_layout)
        
        self._refresh_project_tree()
        
        return widget
    
    def _create_editor_panel(self) -> QWidget:
        """Create code editor panel with breakpoint support."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Editor tabs
        self.editor_tabs = QTabWidget()
        
        # Main editor with breakpoints
        self.editor = CodeEditor()
        self.editor.setFont(QFont("Consolas", 10))
        self.highlighter = STSyntaxHighlighter(self.editor.document())
        
        self.editor_tabs.addTab(self.editor, "No Program Loaded")
        
        layout.addWidget(self.editor_tabs)
        
        return widget
    
    def _create_variable_panel(self) -> QWidget:
        """Create variable inspector panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("Variables"))
        
        self.var_table = QTableWidget()
        self.var_table.setColumnCount(6)  # Added Forced and Actions columns
        self.var_table.setHorizontalHeaderLabels(["Name", "Type", "Value", "Quality", "Forced", "Actions"])
        self.var_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.var_table.customContextMenuRequested.connect(self._show_variable_context_menu)
        layout.addWidget(self.var_table)
        
        return widget
    
    def _create_watch_panel(self) -> QWidget:
        """Create watch expressions panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Add watch input
        input_layout = QHBoxLayout()
        self.watch_input = QLineEdit()
        self.watch_input.setPlaceholderText("Enter expression...")
        input_layout.addWidget(self.watch_input)
        
        btn_add_watch = QPushButton("+")
        btn_add_watch.clicked.connect(self._add_watch_expression)
        input_layout.addWidget(btn_add_watch)
        layout.addLayout(input_layout)
        
        # Watch list
        self.watch_list = QTableWidget()
        self.watch_list.setColumnCount(3)
        self.watch_list.setHorizontalHeaderLabels(["Expression", "Value", "Error"])
        layout.addWidget(self.watch_list)
        
        # Remove button
        btn_remove_watch = QPushButton("Remove Selected")
        btn_remove_watch.clicked.connect(self._remove_watch_expression)
        layout.addWidget(btn_remove_watch)
        
        return widget
    
    def _create_callstack_panel(self) -> QWidget:
        """Create call stack panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(QLabel("Call Stack"))
        
        self.callstack_list = QListWidget()
        layout.addWidget(self.callstack_list)
        
        return widget
    
    def _setup_menubar(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        save_action = QAction("Save Program", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_program)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("Export Program...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_program)
        file_menu.addAction(export_action)
        
        import_action = QAction("Import Program...", self)
        import_action.setShortcut(QKeySequence("Ctrl+I"))
        import_action.triggered.connect(self._import_program)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        
        # PLC menu
        plc_menu = menubar.addMenu("PLC")
        
        compile_action = QAction("Compile Program", self)
        compile_action.setShortcut(QKeySequence("F7"))
        compile_action.triggered.connect(self._compile_program)
        plc_menu.addAction(compile_action)
        
        plc_menu.addSeparator()
        
        run_action = QAction("Start PLC (RUN)", self)
        run_action.setShortcut(QKeySequence("F5"))
        run_action.triggered.connect(self._start_plc)
        plc_menu.addAction(run_action)
        
        stop_action = QAction("Stop PLC", self)
        stop_action.setShortcut(QKeySequence("Shift+F5"))
        stop_action.triggered.connect(self._stop_plc)
        plc_menu.addAction(stop_action)
        
        reset_action = QAction("Reset PLC", self)
        reset_action.triggered.connect(self._reset_plc)
        plc_menu.addAction(reset_action)
    
    def _setup_toolbar(self):
        """Setup toolbar with debugging controls."""
        toolbar = QToolBar("PLC Controls")
        self.addToolBar(toolbar)
        
        # Mode indicator
        self.mode_label = QLabel("STOP")
        self.mode_label.setStyleSheet("QLabel { background-color: #A1260D; color: white; padding: 5px 15px; }")
        toolbar.addWidget(self.mode_label)
        
        toolbar.addSeparator()
        
        # Compile button
        btn_compile = QPushButton("🔨 Compile (F7)")
        btn_compile.clicked.connect(self._compile_program)
        btn_compile.setStyleSheet("QPushButton { background-color: #16825D; color: white; padding: 5px 15px; }")
        toolbar.addWidget(btn_compile)
        
        # Run button
        btn_run = QPushButton("▶ RUN (F5)")
        btn_run.clicked.connect(self._start_plc)
        btn_run.setStyleSheet("QPushButton { background-color: #0E639C; color: white; padding: 5px 15px; }")
        toolbar.addWidget(btn_run)
        
        # Debug button
        btn_debug = QPushButton("🐛 DEBUG")
        btn_debug.clicked.connect(self._start_debug)
        btn_debug.setStyleSheet("QPushButton { background-color: #B7410E; color: white; padding: 5px 15px; }")
        toolbar.addWidget(btn_debug)
        
        # Stop button
        btn_stop = QPushButton("⏹ STOP")
        btn_stop.clicked.connect(self._stop_plc)
        btn_stop.setStyleSheet("QPushButton { background-color: #A1260D; color: white; padding: 5px 15px; }")
        toolbar.addWidget(btn_stop)
        
        toolbar.addSeparator()
        
        # Debug toolbar
        debug_toolbar = QToolBar("Debug Controls")
        self.addToolBar(debug_toolbar)
        
        # Toggle breakpoint
        btn_breakpoint = QPushButton("🔴 Breakpoint (F9)")
        btn_breakpoint.clicked.connect(self._toggle_breakpoint)
        debug_toolbar.addWidget(btn_breakpoint)
        
        # Step Into
        btn_step_into = QPushButton("⤵ Step Into (F11)")
        btn_step_into.clicked.connect(self._step_into)
        debug_toolbar.addWidget(btn_step_into)
        
        # Step Over
        btn_step_over = QPushButton("⤋ Step Over (F10)")
        btn_step_over.clicked.connect(self._step_over)
        debug_toolbar.addWidget(btn_step_over)
        
        # Continue
        btn_continue = QPushButton("▶▶ Continue (F8)")
        btn_continue.clicked.connect(self._continue_debug)
        debug_toolbar.addWidget(btn_continue)
        
        debug_toolbar.addSeparator()
        
        # Verbose logging toggle
        self.verbose_check = QCheckBox("📋 Verbose Logging")
        self.verbose_check.setToolTip("Enable detailed execution logging")
        self.verbose_check.stateChanged.connect(self._toggle_verbose_logging)
        debug_toolbar.addWidget(self.verbose_check)
        
        debug_toolbar.addSeparator()
        
        # Scan time display
        self.scan_label = QLabel("Scan: 0.0ms")
        toolbar.addWidget(self.scan_label)
        
        # Setup keyboard shortcuts
        self._setup_debug_shortcuts()
    
    def _refresh_project_tree(self):
        """Refresh project tree with programs and tasks."""
        self.project_tree.clear()
        
        # Programs
        programs_item = QTreeWidgetItem(self.project_tree, ["Programs"])
        for program in self.plc_ext.programs:
            prog_item = QTreeWidgetItem(programs_item, [
                f"{program.name} ({program.language.value})"
            ])
            prog_item.setData(0, Qt.UserRole, program)
        
        # Tasks
        tasks_item = QTreeWidgetItem(self.project_tree, ["Tasks"])
        for task in self.plc_ext.tasks:
            task_item = QTreeWidgetItem(tasks_item, [
                f"{task.name} (P{task.priority}, {task.interval_ms}ms)"
            ])
            task_item.setData(0, Qt.UserRole, task)
        
        self.project_tree.expandAll()
    
    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click on tree item."""
        data = item.data(0, Qt.UserRole)
        if isinstance(data, PLCProgram):
            self._load_program(data)
    
    def _load_program(self, program: PLCProgram):
        """Load program into editor."""
        self.current_program = program
        self.editor.setPlainText(program.source_code)
        self.editor_tabs.setTabText(0, program.name)
        self._update_variable_table()
        self._log(f"Loaded program: {program.name}")
    
    def _new_program(self):
        """Create new program."""
        name, ok = QInputDialog.getText(self, "New Program", "Program name:")
        if not ok or not name:
            return
        
        # Generate unique ID
        import uuid
        program_id = f"prog_{uuid.uuid4().hex[:8]}"
        
        # Create program with template
        template = """PROGRAM NewProgram
VAR
    counter : INT := 0;
END_VAR

(* Main program logic *)
counter := counter + 1;

END_PROGRAM
"""
        program = PLCProgram(
            program_id=program_id,
            name=name,
            language=IEC61131Language.STRUCTURED_TEXT,
            source_code=template
        )
        
        self.plc_ext.add_program(program)
        self._refresh_project_tree()
        self._load_program(program)
        self._log(f"Created program: {name}")
    
    def _new_task(self):
        """Create new task."""
        name, ok = QInputDialog.getText(self, "New Task", "Task name:")
        if not ok or not name:
            return
        
        import uuid
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        task = PLCTask(
            task_id=task_id,
            name=name,
            task_type=TaskType.CYCLIC,
            priority=10,
            interval_ms=100.0
        )
        
        self.plc_ext.add_task(task)
        self._refresh_project_tree()
        self._log(f"Created task: {name}")
    
    def _save_program(self):
        """Save current program."""
        if not self.current_program:
            QMessageBox.warning(self, "No Program", "No program loaded to save.")
            return
        
        self.current_program.source_code = self.editor.toPlainText()
        self._log(f"Saved program: {self.current_program.name}")
    
    def _export_program(self):
        """Export current program to .st file."""
        if not self.current_program:
            QMessageBox.warning(self, "No Program", "No program loaded to export.")
            return
        
        from PySide6.QtWidgets import QFileDialog
        
        # Save first
        self._save_program()
        
        # Get file path
        default_name = f"{self.current_program.name}.st"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Program", default_name, "Structured Text (*.st);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.current_program.source_code)
                self._log(f"✓ Exported program to: {file_path}")
                QMessageBox.information(self, "Export Success", f"Program exported to:\n{file_path}")
            except Exception as e:
                self._log(f"✗ Export failed: {e}", "error")
                QMessageBox.critical(self, "Export Error", f"Failed to export program:\n{e}")
    
    def _import_program(self):
        """Import program from .st file."""
        from PySide6.QtWidgets import QFileDialog
        
        # Get file path
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Program", "", "Structured Text (*.st);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()
                
                # Get program name
                program_name = Path(file_path).stem
                existing_names = [p.name for p in self.plc_ext.programs]
                
                if program_name in existing_names:
                    # Ask for new name
                    program_name, ok = QInputDialog.getText(
                        self, "Program Name", 
                        f"Program '{program_name}' already exists. Enter a new name:",
                        text=f"{program_name}_imported"
                    )
                    if not ok or not program_name:
                        return
                
                # Create new program
                new_program = PLCProgram(
                    program_id=f"PRG_{program_name}",
                    name=program_name,
                    language=IEC61131Language.ST,
                    source_code=source_code
                )
                
                self.plc_ext.add_program(new_program)
                self._update_program_tree()
                self._load_program(new_program)
                
                self._log(f"✓ Imported program: {program_name}")
                QMessageBox.information(self, "Import Success", f"Program '{program_name}' imported successfully!")
                
            except Exception as e:
                self._log(f"✗ Import failed: {e}", "error")
                QMessageBox.critical(self, "Import Error", f"Failed to import program:\n{e}")
    
    def _compile_program(self):
        """Compile current program."""
        if not self.current_program:
            QMessageBox.warning(self, "No Program", "No program loaded to compile.")
            return
        
        # Save first
        self._save_program()
        
        # Compile
        self._log(f"Compiling {self.current_program.name}...")
        result = self.compiler.compile(self.current_program)
        
        if result.success:
            self._log(f"✓ Compilation successful")
            # Set compiled bytecode on program
            self.current_program.compiled_code = result.bytecode
            if result.warnings:
                for warn in result.warnings:
                    self._log(f"  Warning line {warn.line}: {warn.message}", "warning")
            QMessageBox.information(self, "Compile Success", "Program compiled successfully!")
        else:
            self._log(f"✗ Compilation failed")
            for error in result.errors:
                self._log(f"  Error line {error.line}: {error.message}", "error")
            QMessageBox.critical(self, "Compile Error", f"Compilation failed with {len(result.errors)} errors.")
        
        # Update variable table
        self._update_variable_table()
    
    def _start_plc(self):
        """Start PLC runtime."""
        if self.plc_ext.operating_mode == PLCMode.RUN:
            self._log("PLC already running")
            return
        
        # Ensure at least one program is compiled
        compiled_count = sum(1 for p in self.plc_ext.programs if p.compiled_code)
        if compiled_count == 0:
            QMessageBox.warning(self, "No Programs", "Compile at least one program before starting PLC.")
            return
        
        # Check if any tasks have programs assigned
        tasks_with_programs = sum(1 for t in self.plc_ext.tasks if t.enabled and len(t.program_ids) > 0)
        if tasks_with_programs == 0:
            msg = f"No tasks have programs assigned!\n\n"
            msg += f"You have {len(self.plc_ext.programs)} program(s) and {len(self.plc_ext.tasks)} task(s),\n"
            msg += f"but no task has any programs in its program_ids list.\n\n"
            msg += f"To fix:\n"
            msg += f"1. Click ⚙️ Task Settings button\n"
            msg += f"2. Select your task\n"
            msg += f"3. Check the programs you want to execute\n"
            msg += f"4. Click OK\n\n"
            msg += f"Do you want to open Task Settings now?"
            
            reply = QMessageBox.question(self, "No Programs Assigned to Tasks", msg,
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._configure_tasks()
            return
        
        if self.runtime.start():
            self._log("PLC started (RUN mode)")
        else:
            self._log("Failed to start PLC", "error")
    
    def _start_debug(self):
        """Start PLC in debug mode."""
        if self.plc_ext.operating_mode == PLCMode.DEBUG:
            self._log("PLC already in DEBUG mode")
            return
        
        # Ensure at least one program is compiled
        compiled_count = sum(1 for p in self.plc_ext.programs if p.compiled_code)
        if compiled_count == 0:
            QMessageBox.warning(self, "No Programs", "Compile at least one program before starting PLC in debug mode.")
            return
        
        # Check if any tasks have programs assigned
        tasks_with_programs = sum(1 for t in self.plc_ext.tasks if t.enabled and len(t.program_ids) > 0)
        if tasks_with_programs == 0:
            msg = f"No tasks have programs assigned!\n\n"
            msg += f"To fix, click ⚙️ Task Settings and assign programs to your tasks.\n\n"
            msg += f"Open Task Settings now?"
            
            reply = QMessageBox.question(self, "No Programs Assigned", msg,
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self._configure_tasks()
            return
        
        if self.runtime.start_debug():
            self._log("PLC started (DEBUG mode)")
        else:
            self._log("Failed to start PLC in debug mode", "error")
    
    def _toggle_verbose_logging(self, state):
        """Toggle verbose execution logging."""
        self.verbose_logging = bool(state)
        self.runtime.verbose_logging = self.verbose_logging
        if self.verbose_logging:
            self._log("✓ Verbose logging ENABLED - detailed execution trace will appear below")
        else:
            self._log("Verbose logging disabled")
    
    def _stop_plc(self):
        """Stop PLC runtime."""
        if self.runtime.stop():
            self._log("PLC stopped")
    
    def _reset_plc(self):
        """Reset PLC from fault."""
        if self.runtime.reset():
            self._log("PLC reset from fault")
        else:
            self._log("PLC not in fault state")
    
    def _update_status(self):
        """Update status indicators."""
        # Mode indicator
        mode = self.plc_ext.operating_mode
        mode_colors = {
            PLCMode.STOP: "#A1260D",
            PLCMode.RUN: "#16825D",
            PLCMode.DEBUG: "#0E639C",
            PLCMode.FAULTED: "#FF0000"
        }
        color = mode_colors.get(mode, "#666666")
        self.mode_label.setText(mode.value.upper())
        self.mode_label.setStyleSheet(f"QLabel {{ background-color: {color}; color: white; padding: 5px 15px; }}")
        
        # Scan time with statistics
        self.scan_label.setText(f"Scan: {self.plc_ext.scan_time_ms:.1f}ms")
        
        # Update scan statistics
        if hasattr(self.runtime, 'scan_times') and self.runtime.scan_times:
            min_scan = min(self.runtime.scan_times)
            avg_scan = sum(self.runtime.scan_times) / len(self.runtime.scan_times)
            max_scan = max(self.runtime.scan_times)
            self.stats_label.setText(f"Min/Avg/Max: {min_scan:.1f}/{avg_scan:.1f}/{max_scan:.1f}ms")
            
            # Visual warning if scan time exceeds target
            if max_scan > 100:  # Warning threshold
                self.stats_label.setStyleSheet("QLabel { color: red; }")
            elif max_scan > 50:
                self.stats_label.setStyleSheet("QLabel { color: orange; }")
            else:
                self.stats_label.setStyleSheet("QLabel { color: white; }")
        
        # Update all panels if running
        if mode in (PLCMode.RUN, PLCMode.DEBUG) and self.current_program:
            self._update_variable_table()
            self._update_watch_list()
            self._update_callstack()
    
    def _update_variable_table(self):
        """Update variable table with current values and force status."""
        if not self.current_program:
            self.var_table.setRowCount(0)
            return
        
        all_vars = (
            self.current_program.input_variables.variables +
            self.current_program.output_variables.variables +
            self.current_program.local_variables.variables
        )
        
        self.var_table.setRowCount(len(all_vars))
        
        for i, var in enumerate(all_vars):
            # Name
            self.var_table.setItem(i, 0, QTableWidgetItem(var.name))
            
            # Type
            self.var_table.setItem(i, 1, QTableWidgetItem(var.data_type.value))
            
            # Value (show forced value if forced)
            if var.forced:
                value_text = f"{var.forced_value} (forced)"
                value_item = QTableWidgetItem(value_text)
                value_item.setForeground(QColor(255, 165, 0))  # Orange for forced
            else:
                value_item = QTableWidgetItem(str(var.current_value or ""))
            self.var_table.setItem(i, 2, value_item)
            
            # Quality
            self.var_table.setItem(i, 3, QTableWidgetItem(var.quality.value))
            
            # Forced status
            forced_item = QTableWidgetItem("✓" if var.forced else "")
            self.var_table.setItem(i, 4, forced_item)
            
            # Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            
            if var.forced:
                release_btn = QPushButton("Release")
                release_btn.clicked.connect(lambda checked, v=var: self._release_variable(v))
                action_layout.addWidget(release_btn)
            else:
                force_btn = QPushButton("Force")
                force_btn.clicked.connect(lambda checked, v=var: self._force_variable(v))
                action_layout.addWidget(force_btn)
            
            self.var_table.setCellWidget(i, 5, action_widget)
    
    def _show_variable_context_menu(self, position):
        """Show context menu for variable operations."""
        row = self.var_table.rowAt(position.y())
        if row < 0:
            return
        
        if not self.current_program:
            return
        
        all_vars = (
            self.current_program.input_variables.variables +
            self.current_program.output_variables.variables +
            self.current_program.local_variables.variables
        )
        
        if row >= len(all_vars):
            return
        
        var = all_vars[row]
        
        menu = QMenu(self)
        
        if var.forced:
            release_action = QAction("Release Force", self)
            release_action.triggered.connect(lambda: self._release_variable(var))
            menu.addAction(release_action)
        else:
            force_action = QAction("Force Value...", self)
            force_action.triggered.connect(lambda: self._force_variable(var))
            menu.addAction(force_action)
        
        menu.addSeparator()
        
        copy_action = QAction("Copy Value", self)
        copy_action.triggered.connect(lambda: self._copy_variable_value(var))
        menu.addAction(copy_action)
        
        menu.exec(self.var_table.viewport().mapToGlobal(position))
    
    def _force_variable(self, var: PLCVariable):
        """Force a variable to a specific value."""
        current_val = var.forced_value if var.forced else var.current_value
        value, ok = QInputDialog.getText(
            self, 
            f"Force {var.name}",
            f"Enter value for {var.name} ({var.data_type.value}):",
            text=str(current_val or "")
        )
        
        if ok and value:
            try:
                # Convert to appropriate type
                if var.data_type == PLCDataType.BOOL:
                    converted = value.lower() in ('true', '1', 'yes')
                elif var.data_type in (PLCDataType.INT, PLCDataType.DINT, PLCDataType.SINT):
                    converted = int(value)
                elif var.data_type in (PLCDataType.REAL, PLCDataType.LREAL):
                    converted = float(value)
                else:
                    converted = value
                
                var.forced = True
                var.forced_value = converted
                self._log(f"✓ Forced {var.name} = {converted}")
                self._update_variable_table()
            except ValueError as e:
                QMessageBox.warning(self, "Invalid Value", f"Cannot convert '{value}' to {var.data_type.value}")
    
    def _release_variable(self, var: PLCVariable):
        """Release a forced variable."""
        var.forced = False
        var.forced_value = None
        self._log(f"✓ Released {var.name}")
        self._update_variable_table()
    
    def _copy_variable_value(self, var: PLCVariable):
        """Copy variable value to clipboard."""
        from PySide6.QtWidgets import QApplication
        value = var.forced_value if var.forced else var.current_value
        QApplication.clipboard().setText(str(value))
        self._log(f"Copied {var.name} = {value}")
    
    def _setup_debug_shortcuts(self):
        """Setup keyboard shortcuts for debugging."""
        # F9: Toggle breakpoint
        QAction(self).setShortcut(QKeySequence("F9"))
        self.addAction(self.findChild(QAction))
        
        # F8: Continue
        continue_action = QAction(self)
        continue_action.setShortcut(QKeySequence("F8"))
        continue_action.triggered.connect(self._continue_debug)
        self.addAction(continue_action)
        
        # F10: Step Over
        step_over_action = QAction(self)
        step_over_action.setShortcut(QKeySequence("F10"))
        step_over_action.triggered.connect(self._step_over)
        self.addAction(step_over_action)
        
        # F11: Step Into
        step_into_action = QAction(self)
        step_into_action.setShortcut(QKeySequence("F11"))
        step_into_action.triggered.connect(self._step_into)
        self.addAction(step_into_action)
        
        # F9 action
        breakpoint_action = QAction(self)
        breakpoint_action.setShortcut(QKeySequence("F9"))
        breakpoint_action.triggered.connect(self._toggle_breakpoint)
        self.addAction(breakpoint_action)
    
    def _toggle_breakpoint(self):
        """Toggle breakpoint at current line."""
        if not self.current_program:
            return
        
        line = self.editor.get_line_at_cursor()
        self.editor.toggle_breakpoint(line)
        
        # Sync with debug engine
        self.runtime.debug_engine.toggle_breakpoint(self.current_program.program_id, line)
        
        if line in self.editor.breakpoints:
            self._log(f"✓ Breakpoint set at line {line}")
        else:
            self._log(f"✗ Breakpoint removed at line {line}")
    
    def _step_into(self):
        """Step into next statement."""
        if self.plc_ext.operating_mode != PLCMode.DEBUG:
            self._log("PLC must be in DEBUG mode to step", "warning")
            return
        
        self.runtime.debug_engine.step_into()
        self._log("⤵ Step into...")
        QTimer.singleShot(100, self._update_debug_ui)
    
    def _step_over(self):
        """Step over current statement."""
        if self.plc_ext.operating_mode != PLCMode.DEBUG:
            self._log("PLC must be in DEBUG mode to step", "warning")
            return
        
        self.runtime.debug_engine.step_over()
        self._log("⏭ Step over...")
        QTimer.singleShot(100, self._update_debug_ui)
    
    def _continue_debug(self):
        """Continue execution from breakpoint."""
        if self.plc_ext.operating_mode != PLCMode.DEBUG:
            self._log("PLC must be in DEBUG mode to continue", "warning")
            return
        
        self.runtime.debug_engine.continue_execution()
        self._log("▶ Continuing execution...")
    
    def _add_watch_expression(self):
        """Add watch expression."""
        expression = self.watch_input.text().strip()
        if not expression:
            return
        
        self.runtime.debug_engine.add_watch(expression)
        self._update_watch_list()
        self.watch_input.clear()
        self._log(f"Added watch: {expression}")
    
    def _remove_watch_expression(self):
        """Remove selected watch expression."""
        current_row = self.watch_list.currentRow()
        if current_row < 0:
            return
        
        expression = self.watch_list.item(current_row, 0).text()
        self.runtime.debug_engine.remove_watch(expression)
        self._update_watch_list()
        self._log(f"Removed watch: {expression}")
    
    def _update_watch_list(self):
        """Update watch expressions display."""
        if not self.current_program:
            return
        
        # Update watch values from current program context
        if self.plc_ext.operating_mode in (PLCMode.RUN, PLCMode.DEBUG):
            ctx = self.runtime._program_contexts.get(self.current_program.program_id, {})
            self.runtime.debug_engine.update_watches(ctx)
        
        watches = self.runtime.debug_engine.watch_expressions
        self.watch_list.setRowCount(len(watches))
        
        for i, watch in enumerate(watches):
            self.watch_list.setItem(i, 0, QTableWidgetItem(watch.expression))
            self.watch_list.setItem(i, 1, QTableWidgetItem(str(watch.value) if watch.value is not None else ""))
            self.watch_list.setItem(i, 2, QTableWidgetItem(watch.error or ""))
    
    def _update_callstack(self):
        """Update call stack display."""
        self.callstack_list.clear()
        
        for frame in self.runtime.debug_engine.call_stack:
            text = f"{frame.program_name} (Line {frame.line})"
            self.callstack_list.addItem(text)
    
    def _log(self, message: str, level: str = "info"):
        """Log message to output console."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "info": "white",
            "warning": "yellow",
            "error": "red"
        }
        color = color_map.get(level, "white")
        
        self.output_console.append(f'<span style="color: {color}">[{timestamp}] {message}</span>')
    
    def _plc_log(self, level: str, message: str):
        """Log callback for PLCRuntime - routes to PLC IDE's output console."""
        self._log(message, level)
    
    def _update_debug_ui(self):
        """Update debug UI elements after step."""
        # Update current line highlight
        current_line = self.runtime.debug_engine.current_line
        self.code_editor.current_debug_line = current_line
        self.code_editor.line_number_area.update()
        
        # Scroll to current line if set
        if current_line:
            cursor = self.code_editor.textCursor()
            cursor.setPosition(0)
            cursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, current_line - 1)
            self.code_editor.setTextCursor(cursor)
            self.code_editor.centerCursor()
        
        QTimer.singleShot(100, self._update_callstack)
        QTimer.singleShot(100, self._update_watch_list)
        QTimer.singleShot(100, self._update_variable_table)
    
    def _configure_tasks(self):
        """Open task configuration dialog."""
        from PySide6.QtWidgets import QDialog, QFormLayout, QSpinBox, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Task Configuration")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Add warning label about program assignment
        warning_label = QLabel("📋 Tasks execute programs. Check programs below to assign them to this task.\n"
                              "⚠️ Tasks with NO programs assigned will run but do NOTHING!")
        warning_label.setStyleSheet("QLabel { background-color: #FFF3CD; padding: 10px; border: 1px solid #FFC107; border-radius: 3px; }")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)
        
        form_layout = QFormLayout()
        
        # Get or create main task
        task = None
        if self.plc_ext.tasks:
            task = self.plc_ext.tasks[0]
        else:
            # Create default task
            task = PLCTask(
                task_id="MainTask",
                name="MainTask",
                task_type=TaskType.CYCLIC,
                interval_ms=100.0,
                program_ids=[]
            )
            self.plc_ext.add_task(task)
        
        # Task Name
        task_name = QLineEdit(task.name)
        form_layout.addRow("Task Name:", task_name)
        
        # Task Type
        task_type_combo = QComboBox()
        task_type_combo.addItems([t.value for t in TaskType])
        task_type_combo.setCurrentText(task.task_type.value)
        form_layout.addRow("Task Type:", task_type_combo)
        
        # Interval (ms)
        interval_spin = QSpinBox()
        interval_spin.setRange(1, 10000)
        interval_spin.setValue(int(task.interval_ms))
        interval_spin.setSuffix(" ms")
        form_layout.addRow("Scan Interval:", interval_spin)
        
        # Priority
        priority_spin = QSpinBox()
        priority_spin.setRange(0, 255)
        priority_spin.setValue(task.priority)
        form_layout.addRow("Priority:", priority_spin)
        
        # Enabled checkbox
        enabled_check = QCheckBox()
        enabled_check.setChecked(task.enabled)
        form_layout.addRow("Enabled:", enabled_check)
        
        # Program assignment
        # Ensure current program is registered if user created/edited before opening task config
        if not self.plc_ext.programs and self.current_program is not None:
            self.plc_ext.add_program(self.current_program)

        program_list = QListWidget()
        program_list.setSelectionMode(QListWidget.MultiSelection)
        for prog in self.plc_ext.programs:
            item = QListWidgetItem(prog.name)
            item.setData(Qt.UserRole, prog.program_id)
            program_list.addItem(item)
            if prog.program_id in task.program_ids:
                item.setSelected(True)
        form_layout.addRow("Assigned Programs:", program_list)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec():
            # Save settings
            task.name = task_name.text()
            task.task_type = TaskType(task_type_combo.currentText())
            task.interval_ms = float(interval_spin.value())
            task.priority = priority_spin.value()
            task.enabled = enabled_check.isChecked()
            
            # Update program assignments
            task.program_ids = []
            for i in range(program_list.count()):
                item = program_list.item(i)
                if item.isSelected():
                    task.program_ids.append(item.data(Qt.UserRole))
            
            self._log(f"Task '{task.name}' configured: {task.task_type.value}, {task.interval_ms}ms")
            self._refresh_project_tree()
