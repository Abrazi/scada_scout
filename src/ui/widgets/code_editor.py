"""
Advanced code editor widget with line numbers, breakpoints, and execution highlighting.
"""
from PySide6.QtWidgets import QWidget, QPlainTextEdit, QTextEdit, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import (
    QColor, QPainter, QTextFormat, QFont, QTextCursor, QSyntaxHighlighter,
    QTextCharFormat, QPalette, QFontMetrics
)
import re
from typing import Dict, Set


class LineNumberArea(QWidget):
    """Widget for displaying line numbers and breakpoints."""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)
    
    def mousePressEvent(self, event):
        """Toggle breakpoint on click."""
        if event.button() == Qt.LeftButton:
            # Calculate line number from click position
            block_number = self.editor.firstVisibleBlock().blockNumber()
            top = self.editor.blockBoundingGeometry(
                self.editor.firstVisibleBlock()
            ).translated(self.editor.contentOffset()).top()
            
            block = self.editor.firstVisibleBlock()
            while block.isValid():
                if top <= event.pos().y() < top + self.editor.blockBoundingRect(block).height():
                    line_number = block_number + 1
                    self.editor.toggle_breakpoint_at_line(line_number)
                    break
                
                block = block.next()
                top += self.editor.blockBoundingRect(block).height()
                block_number += 1


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Define formats
        self.formats = {}
        
        # Keyword format
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))  # Blue
        keyword_format.setFontWeight(QFont.Bold)
        self.formats['keyword'] = keyword_format
        
        # String format
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))  # Orange
        self.formats['string'] = string_format
        
        # Comment format
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))  # Green
        comment_format.setFontItalic(True)
        self.formats['comment'] = comment_format
        
        # Number format
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))  # Light green
        self.formats['number'] = number_format
        
        # Function format
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#DCDCAA"))  # Yellow
        self.formats['function'] = function_format
        
        # Decorator format
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#4EC9B0"))  # Cyan
        self.formats['decorator'] = decorator_format
        
        # Define patterns
        self.rules = []
        
        # Keywords
        keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
            'True', 'try', 'while', 'with', 'yield', 'async', 'await'
        ]
        keyword_pattern = r'\b(' + '|'.join(keywords) + r')\b'
        self.rules.append((re.compile(keyword_pattern), self.formats['keyword']))
        
        # Built-in functions
        builtins = [
            'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'dir',
            'enumerate', 'filter', 'float', 'format', 'frozenset', 'getattr',
            'hasattr', 'hash', 'hex', 'id', 'input', 'int', 'isinstance',
            'issubclass', 'iter', 'len', 'list', 'map', 'max', 'min',
            'next', 'object', 'oct', 'open', 'ord', 'pow', 'print',
            'range', 'repr', 'reversed', 'round', 'set', 'setattr',
            'slice', 'sorted', 'str', 'sum', 'super', 'tuple', 'type',
            'vars', 'zip'
        ]
        builtin_pattern = r'\b(' + '|'.join(builtins) + r')\b'
        self.rules.append((re.compile(builtin_pattern), self.formats['function']))
        
        # Numbers
        number_pattern = r'\b[+-]?[0-9]+\.?[0-9]*\b'
        self.rules.append((re.compile(number_pattern), self.formats['number']))
        
        # Strings (single and double quotes)
        string_patterns = [
            r'"[^"\\]*(\\.[^"\\]*)*"',
            r"'[^'\\]*(\\.[^'\\]*)*'",
            r'""".*?"""',
            r"'''.*?'''"
        ]
        for pattern in string_patterns:
            self.rules.append((re.compile(pattern), self.formats['string']))
        
        # Comments
        comment_pattern = r'#[^\n]*'
        self.rules.append((re.compile(comment_pattern), self.formats['comment']))
        
        # Function definitions
        function_pattern = r'\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        self.rules.append((re.compile(function_pattern), self.formats['function']))
        
        # Decorators
        decorator_pattern = r'@[a-zA-Z_][a-zA-Z0-9_.]*'
        self.rules.append((re.compile(decorator_pattern), self.formats['decorator']))
    
    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text."""
        # Apply rules
        for pattern, format_obj in self.rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, format_obj)


class CodeEditor(QPlainTextEdit):
    """
    Code editor with line numbers, breakpoints, and execution highlighting.
    """
    
    breakpoint_toggled = Signal(int, bool)  # line, is_set
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Styling
        self.setFont(QFont("Consolas", 10))
        self.setTabStopDistance(QFontMetrics(self.font()).horizontalAdvance(' ') * 4)
        
        # Dark theme colors
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3E3E3E;
            }
        """)
        
        # Line number area
        self.line_number_area = LineNumberArea(self)
        
        # Breakpoints and execution line
        self.breakpoints: Set[int] = set()
        self.current_execution_line: int = -1
        
        # Syntax highlighter
        self.highlighter = PythonHighlighter(self.document())
        
        # Connect signals
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        
        self.update_line_number_area_width(0)
    
    def line_number_area_width(self):
        """Calculate width needed for line number area."""
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits + 20  # Extra space for breakpoint indicator
        return space
    
    def update_line_number_area_width(self, _):
        """Update the width of the line number area."""
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def update_line_number_area(self, rect, dy):
        """Update the line number area when scrolling."""
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
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )
    
    def line_number_area_paint_event(self, event):
        """Paint line numbers and breakpoint indicators."""
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#252526"))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line_number = block_number + 1
                
                # Draw current execution line background
                if line_number == self.current_execution_line:
                    painter.fillRect(
                        0, int(top), self.line_number_area.width(), 
                        int(self.fontMetrics().height()),
                        QColor("#FFFF00", 50)  # Yellow highlight
                    )
                
                # Draw breakpoint indicator
                if line_number in self.breakpoints:
                    painter.setBrush(QColor("#E51400"))  # Red
                    painter.setPen(Qt.NoPen)
                    circle_size = 12
                    painter.drawEllipse(
                        5, int(top) + (int(self.fontMetrics().height()) - circle_size) // 2,
                        circle_size, circle_size
                    )
                
                # Draw line number
                painter.setPen(QColor("#858585"))
                painter.drawText(
                    25, int(top), self.line_number_area.width() - 30,
                    int(self.fontMetrics().height()),
                    Qt.AlignRight, str(line_number)
                )
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    
    def toggle_breakpoint_at_line(self, line: int):
        """Toggle breakpoint at the specified line."""
        if line in self.breakpoints:
            self.breakpoints.remove(line)
            self.breakpoint_toggled.emit(line, False)
        else:
            self.breakpoints.add(line)
            self.breakpoint_toggled.emit(line, True)
        
        self.line_number_area.update()
    
    def set_breakpoints(self, lines: Set[int]):
        """Set breakpoints at specified lines."""
        self.breakpoints = lines.copy()
        self.line_number_area.update()
    
    def clear_breakpoints(self):
        """Clear all breakpoints."""
        self.breakpoints.clear()
        self.line_number_area.update()
    
    def set_current_execution_line(self, line: int):
        """Highlight the current execution line."""
        self.current_execution_line = line
        
        # Scroll to the line
        if line > 0:
            cursor = QTextCursor(self.document().findBlockByLineNumber(line - 1))
            self.setTextCursor(cursor)
            self.centerCursor()
            
            # Highlight line using ExtraSelection
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#3A3D41")) # VS Code debug line color
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = cursor
            selection.cursor.clearSelection()
            self.setExtraSelections([selection])
        else:
            self.setExtraSelections([])
        
        # Update display
        self.viewport().update()
        self.line_number_area.update()
    
    def clear_current_execution_line(self):
        """Clear the current execution line highlight."""
        self.current_execution_line = -1
        self.setExtraSelections([])
        self.viewport().update()
        self.line_number_area.update()
    
    def get_line_count(self):
        """Get total number of lines."""
        return self.blockCount()
    
    def get_line_text(self, line: int) -> str:
        """Get text of a specific line (1-indexed)."""
        block = self.document().findBlockByLineNumber(line - 1)
        return block.text() if block.isValid() else ""
