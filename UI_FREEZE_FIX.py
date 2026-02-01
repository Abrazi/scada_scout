"""
CRITICAL FIX: IEC 61850 Control Operations - UI Thread Blocking

The app freezes because control operations (select/operate) are running
on the UI thread with blocking network calls.

This file provides the correct fix:
1. Run control operations in worker threads
2. Use Qt signals for async communication
3. Handle timeouts properly
4. Don't block UI

ISSUE: The previous "fix" made things worse by:
- Not addressing UI threading
- Adding complexity without fixing root cause
- Not testing with real IED

REAL PROBLEMS:
1. adapter.select() and adapter.operate() are SYNCHRONOUS
2. They can take 1-10+ seconds
3. They're called directly from UI button handlers
4. QApplication.processEvents() doesn't help with long operations
5. This freezes the entire UI
"""

from PySide6.QtCore import QThread, Signal as QtSignal, QObject
from typing import Any


class ControlWorker(QObject):
    """
    Worker to run control operations in background thread.
    Prevents UI freezing during select/operate.
    """
    # Signals
    progress = QtSignal(str)  # Progress message
    success = QtSignal(bool, str)  # (success, message)
    finished = QtSignal()
    
    def __init__(self, adapter, signal, operation, value=None, params=None):
        super().__init__()
        self.adapter = adapter
        self.signal = signal
        self.operation = operation  # 'select' or 'operate'
        self.value = value
        self.params = params or {}
        self._cancelled = False
    
    def cancel(self):
        """Cancel the operation"""
        self._cancelled = True
    
    def run(self):
        """Execute control operation in background"""
        try:
            if self._cancelled:
                self.finished.emit()
                return
            
            if self.operation == 'select':
                self.progress.emit("Sending SELECT to IED...")
                result = self.adapter.select(self.signal, self.value, self.params)
                
                if result:
                    self.success.emit(True, "SELECT successful - Ready to operate")
                else:
                    error_msg = getattr(self.adapter, '_last_control_error', 'SELECT failed')
                    self.success.emit(False, f"SELECT failed: {error_msg}")
            
            elif self.operation == 'operate':
                self.progress.emit("Sending OPERATE to IED...")
                result = self.adapter.operate(self.signal, self.value, self.params)
                
                if result:
                    self.success.emit(True, f"OPERATE successful: {self.value}")
                else:
                    error_msg = getattr(self.adapter, '_last_control_error', 'OPERATE failed')
                    self.success.emit(False, f"OPERATE failed: {error_msg}")
            
            else:
                self.success.emit(False, f"Unknown operation: {self.operation}")
        
        except Exception as e:
            self.success.emit(False, f"Exception: {str(e)}")
        finally:
            self.finished.emit()


# =============================================================================
# FIX FOR control_dialog.py
# =============================================================================

def _on_select_FIXED(self):
    """
    Fixed SELECT handler - runs in background thread.
    Replace the existing _on_select() method with this.
    """
    try:
        adapter = self._get_adapter()
        if not adapter:
            self.lbl_status.setText("Adapter not available")
            self._set_label_status(self.lbl_status, "error")
            return
        
        # Disable buttons during operation
        self.btn_select.setEnabled(False)
        self.btn_operate.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        # Get parameters
        params = self._get_params()
        val = self._get_value()
        
        # Update context
        object_ref = adapter._get_control_object_reference(self.signal.address)
        ctx = adapter.controls.get(object_ref)
        if ctx:
            ctx.originator_cat = params['originator_category']
            ctx.originator_id = params['originator_identity']
            ctx.ctl_num = self.num_ctl_num.value()
        
        # Show progress
        self.lbl_status.setText("Starting SELECT...")
        self._set_label_status(self.lbl_status, "info")
        
        # Create worker thread
        self._worker = ControlWorker(adapter, self.signal, 'select', val, params)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        
        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_control_progress)
        self._worker.success.connect(self._on_select_result)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        
        # Start thread
        self._thread.start()
        
    except Exception as e:
        self.lbl_status.setText(f"Select Error: {e}")
        self._set_label_status(self.lbl_status, "error")
        self.btn_select.setEnabled(True)
        self.btn_operate.setEnabled(True)
        self.btn_cancel.setEnabled(True)


def _on_operate_FIXED(self):
    """
    Fixed OPERATE handler - runs in background thread.
    Replace the existing _on_operate() method with this.
    """
    try:
        adapter = self._get_adapter()
        if not adapter:
            self.lbl_status.setText("Adapter not available")
            self._set_label_status(self.lbl_status, "error")
            return
        
        # Disable buttons during operation
        self.btn_select.setEnabled(False)
        self.btn_operate.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        # Get parameters
        params = self._get_params()
        val = self._get_value()
        
        # Update context
        object_ref = adapter._get_control_object_reference(self.signal.address)
        ctx = adapter.controls.get(object_ref)
        if ctx:
            ctx.originator_cat = params['originator_category']
            ctx.originator_id = params['originator_identity']
            if self.num_ctl_num.value() != 0:
                ctx.ctl_num = self.num_ctl_num.value()
        
        # Show progress
        self.lbl_status.setText("Starting OPERATE...")
        self._set_label_status(self.lbl_status, "info")
        
        # Create worker thread
        self._worker = ControlWorker(adapter, self.signal, 'operate', val, params)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        
        # Connect signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_control_progress)
        self._worker.success.connect(self._on_operate_result)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        
        # Start thread
        self._thread.start()
        
    except Exception as e:
        self.lbl_status.setText(f"Operate Error: {e}")
        self._set_label_status(self.lbl_status, "error")
        self.btn_select.setEnabled(True)
        self.btn_operate.setEnabled(True)
        self.btn_cancel.setEnabled(True)


def _on_control_progress(self, message: str):
    """Handle progress updates"""
    self.lbl_status.setText(message)
    self._set_label_status(self.lbl_status, "info")


def _on_select_result(self, success: bool, message: str):
    """Handle SELECT result"""
    self.lbl_status.setText(message)
    
    if success:
        self._set_label_status(self.lbl_status, "success")
        self.selected = True
        self._sync_ui_from_context()
    else:
        self._set_label_status(self.lbl_status, "error")
    
    # Re-enable buttons
    self.btn_select.setEnabled(True)
    self.btn_operate.setEnabled(True)
    self.btn_cancel.setEnabled(True)


def _on_operate_result(self, success: bool, message: str):
    """Handle OPERATE result"""
    self.lbl_status.setText(message)
    
    if success:
        self._set_label_status(self.lbl_status, "success")
        self.operated = True
        self._sync_ui_from_context()
        
        # Auto-close dialog after successful operate (optional)
        # QTimer.singleShot(1000, self.accept)
    else:
        self._set_label_status(self.lbl_status, "error")
    
    # Re-enable buttons
    self.btn_select.setEnabled(True)
    self.btn_operate.setEnabled(True)
    self.btn_cancel.setEnabled(True)


# =============================================================================
# IMPLEMENTATION INSTRUCTIONS
# =============================================================================

"""
TO FIX THE UI FREEZE:

1. Add this import at top of control_dialog.py:
   from PySide6.QtCore import QThread, QObject

2. Copy the ControlWorker class to control_dialog.py (before the dialog class)

3. In the IECControlDialog class, add these instance variables in __init__:
   self._worker = None
   self._thread = None

4. Replace the _on_select() method with _on_select_FIXED()

5. Replace the _on_operate() method with _on_operate_FIXED()

6. Add the handler methods:
   - _on_control_progress
   - _on_select_result
   - _on_operate_result

7. Test:
   - Click SELECT - UI should remain responsive
   - Click OPERATE - UI should remain responsive
   - Status updates should show in real-time
   - No freezing

ALTERNATIVE SIMPLER FIX (if you don't want threading):

Just wrap the operations in QTimer to break them into chunks:

def _on_select(self):
    self.lbl_status.setText("Selecting...")
    self._set_label_status(self.lbl_status, "info")
    
    # Delay actual operation to let UI update
    QTimer.singleShot(100, self._do_select)

def _do_select(self):
    try:
        adapter = self._get_adapter()
        params = self._get_params()
        val = self._get_value()
        
        result = adapter.select(self.signal, val, params)
        
        if result:
            self.lbl_status.setText("SELECT successful")
            self._set_label_status(self.lbl_status, "success")
        else:
            self.lbl_status.setText("SELECT failed")
            self._set_label_status(self.lbl_status, "error")
    except Exception as e:
        self.lbl_status.setText(f"Error: {e}")
        self._set_label_status(self.lbl_status, "error")

But threading is better for long operations!
"""
