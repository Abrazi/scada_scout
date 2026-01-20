from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QListWidget, QDoubleSpinBox, QMessageBox, QCompleter
)
from PySide6.QtWidgets import QDialogButtonBox, QListWidgetItem, QCheckBox
from PySide6.QtWidgets import QDialogButtonBox, QListWidgetItem
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class PythonScriptDialog(QDialog):
    """Simple in-app editor for user scripts."""
    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.setWindowTitle("Python Scripts")
        self.resize(900, 600)
        self.setWindowModality(Qt.NonModal)

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Script Name:"))
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g., VoltageBalancer")
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
        self.editor.installEventFilter(self)
        self.editor.setPlaceholderText(
            "# Define tick(ctx)\n"
            "# Example:\n"
            "# def tick(ctx):\n"
            "#     v = ctx.get('Device::SomeAddress')\n"
            "#     ctx.set('Device::OtherAddress', v)\n"
        )
        self._completer = QCompleter(self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.activated.connect(self._insert_completion)
        self._refresh_completer()
        self._highlighter = _PythonHighlighter(self.editor.document())
        # Provide a helpful example script in the editor for users
        EXAMPLE = '''# Example script for SCADA Scout
        # Define a callable named `tick(ctx)` for continuous scripts,
        # or `main(ctx)` / `loop(ctx)` / `tick(ctx)` for one-shot runs.
        # `ctx` exposes helper methods:
        #   - ctx.get(tag_address, default=None)
        #   - ctx.read(tag_address)  # force read (best-effort)
        #   - ctx.set(tag_address, value)  # write value to a tag
        #   - ctx.list_tags(device_name=None)
        #   - ctx.log(level, message)
        #
        # Unique tag addresses are in the form: DeviceName::SignalAddress
        # Examples: IED1::LLN0$XCBR$Pos.stVal  or  ModbusDevice::1:3:40001

        import math

        def tick(ctx):
            # Read a value from another device (non-blocking best-effort)
            src = 'IED1::LLN0$MMXU$Amp.instMag'    # replace with an actual tag
            val = ctx.get(src, 0)

            # Compute something simple
            new_val = math.floor((val or 0) * 1.1)

            # Write result to a target tag
            dst = 'Simulator::holding:40010'  # replace with your target tag
            ok = ctx.set(dst, new_val)

            # Optionally force a read and log result
            forced = ctx.read(src)
            ctx.log('info', f'Computed {new_val} from {src} (forced={forced})')

        # For one-off scripts you can also define `main(ctx)` and run once.
        # def main(ctx):
        #     print('This runs a single time')
        '''
        # Only set example text if editor is empty
        if not self.editor.toPlainText().strip():
            self.editor.setPlainText(EXAMPLE)
        body.addWidget(self.editor, 3)

        right = QVBoxLayout()
        right.addWidget(QLabel("Running Scripts"))
        self.lst_running = QListWidget()
        right.addWidget(self.lst_running, 1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh_running)
        right.addWidget(self.btn_refresh)

        right.addWidget(QLabel("Saved Scripts"))
        self.lst_saved = QListWidget()
        right.addWidget(self.lst_saved, 1)
        self.btn_load = QPushButton("Load")
        self.btn_load.clicked.connect(self._load_selected_saved)
        right.addWidget(self.btn_load)
        self.btn_save = QPushButton("Save Current")
        self.btn_save.clicked.connect(self._save_current)
        right.addWidget(self.btn_save)

        self.btn_insert_tag = QPushButton("Insert Tag (Ctrl+Space)")
        self.btn_insert_tag.clicked.connect(self._show_completions)
        right.addWidget(self.btn_insert_tag)
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
        # Update editor tokens when devices/signals are updated so token text stays current
        try:
            self.device_manager.device_updated.connect(self._on_device_updated)
        except Exception:
            pass
        # Highlight ambiguous tokens on edit
        try:
            self.editor.textChanged.connect(self._highlight_ambiguous_tokens)
        except Exception:
            pass

        # Add batch resolve button
        try:
            self.btn_resolve_all = QPushButton("Resolve All Ambiguous")
            self.btn_resolve_all.clicked.connect(self._batch_resolve)
            right.addWidget(self.btn_resolve_all)
        except Exception:
            pass
    def _on_device_updated(self, device_name: str):
        try:
            code = self._get_code()
            if not code:
                return
            tag_mgr = getattr(self.device_manager._core, '_script_tag_manager', None)
            if not tag_mgr:
                return
            updated = tag_mgr.update_tokens(code)
            if updated != code:
                # Preserve cursor position
                cursor = self.editor.textCursor()
                pos = cursor.position()
                self.editor.blockSignals(True)
                self.editor.setPlainText(updated)
                self.editor.blockSignals(False)
                # Restore cursor to nearest valid position
                new_cursor = self.editor.textCursor()
                new_cursor.setPosition(min(pos, len(updated)))
                self.editor.setTextCursor(new_cursor)
        except Exception:
            pass

    def _highlight_ambiguous_tokens(self):
        try:
            tag_mgr = getattr(self.device_manager._core, '_script_tag_manager', None)
            if not tag_mgr:
                return
            code = self._get_code()
            if not code:
                self.editor.setExtraSelections([])
                return
            tokens = tag_mgr.extract_tokens(code)
            selections = []
            doc = self.editor.document()
            for token in tokens:
                candidates = tag_mgr.get_candidates(token)
                if len(candidates) > 1:
                    # find token occurrences in document and highlight
                    import re
                    for m in re.finditer(re.escape('{{TAG:' + token + '}}'), code):
                        start = m.start()
                        end = m.end()
                        cursor = self.editor.textCursor()
                        cursor.setPosition(start)
                        cursor.setPosition(end, cursor.KeepAnchor)
                        sel = QTextEdit.ExtraSelection()
                        sel.cursor = cursor
                        fmt = sel.format
                        from PySide6.QtGui import QTextCharFormat, QColor
                        fmt = QTextCharFormat()
                        fmt.setBackground(QColor('#fff176'))
                        sel.format = fmt
                        selections.append(sel)
            self.editor.setExtraSelections(selections)
        except Exception:
            pass

    def _batch_resolve(self):
        try:
            tag_mgr = getattr(self.device_manager._core, '_script_tag_manager', None)
            if not tag_mgr:
                QMessageBox.information(self, 'No Tag Manager', 'Tag manager not available.')
                return
            code = self._get_code()
            tokens = tag_mgr.extract_tokens(code)
            ambiguous = [t for t in tokens if len(tag_mgr.get_candidates(t)) > 1]
            if not ambiguous:
                QMessageBox.information(self, 'No Ambiguous Tokens', 'No ambiguous tokens found.')
                return
            # Sequentially prompt user for each ambiguous token in a batch dialog
            for token in ambiguous:
                candidates = tag_mgr.get_candidates(token)
                dlg = CandidateChooserDialog(token, candidates, parent=self)
                if dlg.exec() == QDialog.Accepted:
                    chosen = dlg.selected()
                    if dlg.remember_choice():
                        try:
                            tag_mgr.set_choice(token, chosen)
                        except Exception:
                            pass
                    # Replace token inner with chosen in code while preserving token wrapper
                    code = code.replace('{{TAG:' + token + '}}', '{{TAG:' + chosen + '}}')
                else:
                    # user cancelled; stop batch
                    break
            self.editor.setPlainText(code)
            self._highlight_ambiguous_tokens()
        except Exception:
            QMessageBox.critical(self, 'Batch Resolve Error', 'Failed to resolve ambiguous tokens')

    def _refresh_running(self):
        self.lst_running.clear()
        try:
            for name in self.device_manager.list_user_scripts():
                self.lst_running.addItem(name)
        except Exception:
            pass
        self._refresh_completer()
        self._refresh_saved()

    def _refresh_saved(self):
        self.lst_saved.clear()
        try:
            scripts = self.device_manager.get_saved_scripts()
            for name in scripts.keys():
                self.lst_saved.addItem(name)
        except Exception:
            pass
    def _refresh_completer(self):
        try:
            tags = self.device_manager.list_unique_addresses()
        except Exception:
            tags = []
        self._completer.setModel(None)
        self._completer = QCompleter(tags, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.activated.connect(self._insert_completion)
        self._completer.setWidget(self.editor)

    def _insert_completion(self, text: str):
        cursor = self.editor.textCursor()
        # Insert as a token so it's trackable for future renames
        try:
            token = self.device_manager.make_tag_token(text)
        except Exception:
            token = f"{{{{TAG:{text}}}}}"
        cursor.insertText(token)
        self.editor.setTextCursor(cursor)

    def _show_completions(self):
        self._refresh_completer()
        rect = self.editor.cursorRect()
        rect.setWidth(300)
        self._completer.complete(rect)

    def eventFilter(self, obj, event):
        if obj is self.editor and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space and event.modifiers() == Qt.ControlModifier:
                self._show_completions()
                return True
        return super().eventFilter(obj, event)

    def _get_code(self) -> str:
        return self.editor.toPlainText().strip()

    def _get_name(self) -> str:
        return self.txt_name.text().strip()

    def _run_once(self):
        code = self._get_code()
        if not code:
            QMessageBox.warning(self, "Missing Code", "Paste a script first.")
            return
        try:
            resolved = self._resolve_tokens_with_prompt(code)
            self.device_manager.run_user_script_once(resolved)
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
            # Persist before starting so scripts survive restarts
            self.device_manager.save_user_script(name, code, interval)
            resolved = self._resolve_tokens_with_prompt(code)
            self.device_manager.start_user_script(name, resolved, interval)
            self._refresh_running()
        except Exception as exc:
            QMessageBox.critical(self, "Script Error", str(exc))

    def _save_current(self):
        name = self._get_name()
        code = self._get_code()
        interval = float(self.spin_interval.value())
        if not name:
            QMessageBox.warning(self, "Missing Name", "Provide a script name before saving.")
            return
        try:
            self.device_manager.save_user_script(name, code, interval)
            self._refresh_saved()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def _load_selected_saved(self):
        item = self.lst_saved.currentItem()
        if not item:
            return
        name = item.text()
        try:
            scripts = self.device_manager.get_saved_scripts()
            meta = scripts.get(name)
            if not meta:
                return
            code = meta.get('code', '')
            interval = meta.get('interval', 0.5)
            # Update token internals to current canonical values while preserving token wrappers
            try:
                tag_mgr = getattr(self.device_manager._core, '_script_tag_manager', None)
                if tag_mgr:
                    code = tag_mgr.update_tokens(code)
            except Exception:
                pass
            self.editor.setPlainText(code)
            self.spin_interval.setValue(interval)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    def _resolve_tokens_with_prompt(self, code: str) -> str:
        """Resolve tokens and prompt the user for ambiguous choices via a dialog."""
        tag_mgr = getattr(self.device_manager._core, '_script_tag_manager', None)
        if not tag_mgr:
            return self.device_manager.resolve_script_tokens(code)

        def chooser(token, candidates):
            dlg = CandidateChooserDialog(token, candidates, parent=self)
            if dlg.exec() == QDialog.Accepted:
                chosen = dlg.selected()
                try:
                    # Persist choice if requested
                    if dlg.remember_choice():
                        tag_mgr = getattr(self.device_manager._core, '_script_tag_manager', None)
                        if tag_mgr:
                            tag_mgr.set_choice(token, chosen)
                except Exception:
                    pass
                return chosen
            return None

        try:
            return self.device_manager.resolve_script_tokens_interactive(code, chooser)
        except Exception:
            return self.device_manager.resolve_script_tokens(code)


class CandidateChooserDialog(QDialog):
    def __init__(self, token: str, candidates: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resolve Ambiguous Tag")
        self.resize(480, 300)
        self._token = token
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Multiple matches found for token: {token}"))
        self.lst = QListWidget()
        for c in candidates:
            item = QListWidgetItem(c)
            self.lst.addItem(item)
        layout.addWidget(self.lst)
        self.chk_remember = QCheckBox("Remember my choice for this token")
        layout.addWidget(self.chk_remember)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._selected = None

    def _on_accept(self):
        it = self.lst.currentItem()
        if not it:
            QMessageBox.warning(self, "Select", "Please select a candidate or Cancel")
            return
        self._selected = it.text()
        self.accept()

    def selected(self):
        return self._selected
    
    def remember_choice(self) -> bool:
        return bool(getattr(self, 'chk_remember', None) and self.chk_remember.isChecked())

    def _stop_selected(self):
        item = self.lst_running.currentItem()
        if not item:
            return
        name = item.text()
        try:
            self.device_manager.stop_user_script(name)
            self._refresh_running()
        except Exception as exc:
            QMessageBox.critical(self, "Stop Error", str(exc))


class _PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        def _fmt(color, bold=False, italic=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Bold)
            if italic:
                fmt.setFontItalic(True)
            return fmt

        keyword_format = _fmt("#cc7832", bold=True)
        builtin_format = _fmt("#a9b7c6")
        string_format = _fmt("#6a8759")
        comment_format = _fmt("#808080", italic=True)
        number_format = _fmt("#6897bb")
        decorator_format = _fmt("#bbb529")

        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "False", "finally", "for", "from", "global",
            "if", "import", "in", "is", "lambda", "None", "nonlocal", "not",
            "or", "pass", "raise", "return", "True", "try", "while", "with", "yield"
        ]

        builtins = [
            "abs", "all", "any", "bool", "dict", "enumerate", "float", "int", "len",
            "list", "map", "max", "min", "print", "range", "set", "str", "sum", "tuple"
        ]

        for kw in keywords:
            self._rules.append((rf"\b{kw}\b", keyword_format))
        for bi in builtins:
            self._rules.append((rf"\b{bi}\b", builtin_format))

        self._rules.append((r"#[^\n]*", comment_format))
        self._rules.append((r"\b[0-9]+(\.[0-9]+)?\b", number_format))
        self._rules.append((r"\b@[A-Za-z_][A-Za-z0-9_]*", decorator_format))
        self._rules.append((r"'[^'\\]*(\\.[^'\\]*)*'", string_format))
        self._rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', string_format))

    def highlightBlock(self, text):
        import re
        for pattern, fmt in self._rules:
            for match in re.finditer(pattern, text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)

    def _get_code(self) -> str:
        return self.editor.toPlainText().strip()

    def _get_name(self) -> str:
        return self.txt_name.text().strip()

    def _run_once(self):
        code = self._get_code()
        if not code:
            QMessageBox.warning(self, "Missing Code", "Paste a script first.")
            return
        try:
            self.device_manager.run_user_script_once(code)
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
            self.device_manager.start_user_script(name, code, interval)
            self._refresh_running()
        except Exception as exc:
            QMessageBox.critical(self, "Script Error", str(exc))

    def _stop_selected(self):
        item = self.lst_running.currentItem()
        if not item:
            return
        name = item.text()
        try:
            self.device_manager.stop_user_script(name)
            self._refresh_running()
        except Exception as exc:
            QMessageBox.critical(self, "Stop Error", str(exc))
