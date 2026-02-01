"""
Integration Snippet for IEC 61850 Fixed Control Client

This file shows how to integrate the fixed control client into adapter.py
without completely rewriting the existing implementation.

Option 1: Add as a fallback method
Option 2: Replace the operate method entirely
Option 3: Add as an alternative control method
"""

# =============================================================================
# OPTION 1: Add Fixed Client as Fallback (Recommended - Safest)
# =============================================================================

# Add to imports at top of adapter.py:
from .control_client_fixed import IEC61850ControlClient

# Add to __init__ method:
def __init__(self, *args, **kwargs):
    # ... existing code ...
    self._fixed_control_client = None

# Add new fallback method (or modify existing _fallback_operate):
def _fallback_to_fixed_client(self, signal: Signal, value: Any, object_ref: str) -> bool:
    """
    Fallback to fixed control client when standard methods fail.
    This uses the corrected IEC 61850 control implementation.
    """
    if self.event_logger:
        self.event_logger.info("IEC61850", "Using Fixed Control Client fallback")
    
    try:
        # Create fixed client if needed
        if not self._fixed_control_client:
            self._fixed_control_client = IEC61850ControlClient(
                self.connection,
                event_logger=self.event_logger
            )
        
        # Perform control with automatic SBO handling
        success = self._fixed_control_client.control(object_ref, value)
        
        if success and self.event_logger:
            self.event_logger.transaction("IEC61850", "← FIXED CLIENT SUCCESS")
        
        return success
    except Exception as e:
        if self.event_logger:
            self.event_logger.error("IEC61850", f"Fixed client exception: {e}")
        return False

# Modify existing operate() method to add fallback:
def operate(self, signal: Signal, value: Any, params: dict = None, control_client: Any = None) -> bool:
    """Perform OPERATE phase with fixed client fallback."""
    # ... existing operate implementation ...
    
    # At the end, if all methods failed, add:
    if not success:
        if self.event_logger:
            self.event_logger.warning("IEC61850", "Standard methods failed, trying fixed client...")
        
        object_ref = self._get_control_object_reference(signal.address)
        return self._fallback_to_fixed_client(signal, value, object_ref)
    
    return success


# =============================================================================
# OPTION 2: Replace Operate Method Entirely (Most Aggressive)
# =============================================================================

def operate_v2(self, signal: Signal, value: Any, params: dict = None) -> bool:
    """
    Complete replacement using fixed control client.
    Rename existing operate() to operate_legacy() first.
    """
    if not self.connected or not self.connection:
        return False
    
    try:
        # Get control reference
        object_ref = self._get_control_object_reference(signal.address)
        
        # Create fixed client if needed
        if not self._fixed_control_client:
            self._fixed_control_client = IEC61850ControlClient(
                self.connection,
                event_logger=self.event_logger
            )
        
        # Set custom originator if provided
        if params:
            origin_id = params.get('origin_id', 'scada_scout')
            origin_cat = params.get('origin_cat', 3)
            self._fixed_control_client.set_originator(origin_id, origin_cat)
        
        # Perform control
        success = self._fixed_control_client.control(object_ref, value)
        
        # Update context if success
        if success:
            ctx = self.controls.get(object_ref)
            if ctx:
                ctx.state = ControlState.OPERATED
                ctx.last_operate_time = datetime.now()
        
        return success
    except Exception as e:
        if self.event_logger:
            self.event_logger.error("IEC61850", f"Operate failed: {e}")
        return False


# =============================================================================
# OPTION 3: Add as Alternative Method (Most Flexible)
# =============================================================================

def operate_with_fixed_client(self, signal: Signal, value: Any, params: dict = None) -> bool:
    """
    Alternative operate method using the fixed control client.
    Can be called directly when standard method doesn't work.
    """
    if not self.connected or not self.connection:
        return False
    
    try:
        object_ref = self._get_control_object_reference(signal.address)
        
        # Create fixed client if needed
        if not self._fixed_control_client:
            self._fixed_control_client = IEC61850ControlClient(
                self.connection,
                event_logger=self.event_logger
            )
        
        # Log that we're using the fixed client
        if self.event_logger:
            self.event_logger.info("IEC61850", f"Using fixed control client for {object_ref}")
        
        # Perform control
        return self._fixed_control_client.control(object_ref, value)
    except Exception as e:
        if self.event_logger:
            self.event_logger.error("IEC61850", f"Fixed client failed: {e}")
        return False


# =============================================================================
# USAGE IN UI/DIALOGS
# =============================================================================

# In control_dialog.py or similar:

def perform_control_action(self):
    """Execute control operation from UI"""
    
    # Get adapter instance
    adapter = self.device_manager.get_adapter(self.device_name)
    
    if not adapter or not adapter.connected:
        self.show_error("Device not connected")
        return
    
    # Get control parameters from UI
    control_ref = self.get_selected_control_reference()  # e.g., "LD0/CSWI1.Pos"
    value = self.get_control_value()  # True/False or integer
    
    # Option A: Use existing operate method (will use fallback automatically)
    signal = Signal(
        name=control_ref,
        address=control_ref,
        signal_type=SignalType.BINARY,
        access="RW"
    )
    success = adapter.operate(signal, value)
    
    # Option B: Use fixed client directly
    # from protocols.iec61850.control_client_fixed import IEC61850ControlClient
    # client = IEC61850ControlClient(adapter.connection, adapter.event_logger)
    # success = client.control(control_ref, value)
    
    # Option C: Use alternative method (if you added option 3 above)
    # success = adapter.operate_with_fixed_client(signal, value)
    
    # Show result
    if success:
        self.show_success(f"Control operation successful: {value}")
        self.read_back_status()  # Verify
    else:
        self.show_error("Control operation failed")


# =============================================================================
# TESTING THE INTEGRATION
# =============================================================================

def test_integration():
    """
    Test the integrated fixed control client.
    Run this after adding to adapter.py
    """
    from src.core.device_manager_core import DeviceManagerCore
    from src.models.device_models import DeviceConfig, DeviceType
    
    # Create device manager
    manager = DeviceManagerCore()
    
    # Add IEC 61850 device
    config = DeviceConfig(
        name="TestIED",
        ip_address="192.168.1.100",
        port=102,
        device_type=DeviceType.IEC61850
    )
    
    device = manager.add_device(config)
    
    # Connect
    if not manager.connect_device("TestIED"):
        print("Connection failed")
        return
    
    print("Connected successfully")
    
    # Get adapter
    adapter = device.adapter
    
    # Test control
    from src.models.device_models import Signal, SignalType
    
    control_signal = Signal(
        name="Breaker Position",
        address="LD0/CSWI1.Pos",
        signal_type=SignalType.BINARY,
        access="RW"
    )
    
    # Try control operation
    print("Attempting control operation...")
    success = adapter.operate(control_signal, True)
    
    if success:
        print("✓ Control operation successful!")
    else:
        print("✗ Control operation failed")
    
    # Verify
    import time
    time.sleep(0.5)
    result_signal = adapter.read_signal(control_signal)
    if result_signal:
        print(f"Current value: {result_signal.value}")
    
    # Disconnect
    manager.disconnect_device("TestIED")


# =============================================================================
# RECOMMENDED INTEGRATION STEPS
# =============================================================================

"""
1. Add import to adapter.py:
   from .control_client_fixed import IEC61850ControlClient

2. Add instance variable in __init__:
   self._fixed_control_client = None

3. Choose integration approach:
   - SAFEST: Add Option 1 fallback
   - CLEANEST: Use Option 3 alternative method
   - SIMPLEST: Use fixed client directly in UI code

4. Test with:
   python test_control_fixed.py <ip> <control_ref> <value>

5. Monitor logs for:
   - "Using Fixed Control Client" message
   - "FIXED CLIENT SUCCESS" transaction
   - Any error messages

6. If successful:
   - Test with various control objects
   - Test both SBO and direct control models
   - Test with different IED vendors

7. Document:
   - Update user guide with control instructions
   - Add troubleshooting section
   - Note any vendor-specific quirks
"""
