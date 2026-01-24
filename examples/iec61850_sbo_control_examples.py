"""
IEC 61850 SBO (Select Before Operate) Control Examples for SCADA Scout
=======================================================================

This file contains examples of how to use the ctx.send_command() method
to perform IEC 61850 control operations from Python scripts.

The send_command() method automatically handles:
- SBO (Select Before Operate) workflow for IEDs with ctlModel=2 or 4
- Direct control for IEDs with ctlModel=1 or 3
- Proper ctlNum handling and originator information
- Fallback methods if ControlObjectClient API is unavailable

Note: Replace the device names and addresses with actual values from your system.
      Use Ctrl+Space in the script editor to see available tag completions.
"""

# ============================================================================
# Example 1: Simple Circuit Breaker Control (SBO Automatic)
# ============================================================================
def example_close_breaker(ctx):
    """Close a circuit breaker using automatic SBO workflow."""
    # Replace with your actual IED name and control point
    breaker_control = 'IED1::simpleIOGenericIO/CSWI1.Pos'
    
    # Send command - SBO workflow is handled automatically
    success = ctx.send_command(breaker_control, True)
    
    if success:
        ctx.log('info', f'Successfully closed breaker: {breaker_control}')
    else:
        ctx.log('error', f'Failed to close breaker: {breaker_control}')
    
    return success


# ============================================================================
# Example 2: Circuit Breaker with Custom SBO Timeout
# ============================================================================
def example_breaker_custom_timeout(ctx):
    """
    Control a breaker with custom SBO timeout.
    Default is 100ms, but some IEDs may require more time.
    """
    breaker_control = 'IED1::simpleIOGenericIO/CSWI1.Pos'
    
    # Custom parameters
    params = {
        'sbo_timeout': 200,  # Wait 200ms between SELECT and OPERATE
        'originator_id': 'SCADA_AUTO',  # Custom originator name
        'originator_cat': 3  # 3 = Remote control
    }
    
    # Open breaker (False = open)
    success = ctx.send_command(breaker_control, False, params=params)
    
    if success:
        ctx.log('info', f'Breaker opened with custom timeout')
    
    return success


# ============================================================================
# Example 3: Controlling Multiple Breakers in Sequence
# ============================================================================
def example_sequential_control(ctx):
    """Control multiple circuit breakers in sequence."""
    breakers = [
        'IED1::simpleIOGenericIO/CSWI1.Pos',
        'IED1::simpleIOGenericIO/CSWI2.Pos',
        'IED1::simpleIOGenericIO/CSWI3.Pos'
    ]
    
    for breaker in breakers:
        ctx.log('info', f'Closing {breaker}...')
        success = ctx.send_command(breaker, True)
        
        if success:
            ctx.log('info', f'  ✓ Success')
        else:
            ctx.log('error', f'  ✗ Failed')
            break  # Stop on first failure
        
        # Wait a bit between operations
        ctx.sleep(0.5)
    
    return True


# ============================================================================
# Example 4: External Client Control (Real IED)
# ============================================================================
def example_external_ied_control(ctx):
    """
    Control a real external IED connected to your network.
    
    Prerequisites:
    1. Add the IED connection in SCADA Scout (File > Connect to IED)
    2. Browse the IED to discover available control points
    3. Use Ctrl+Space to see tag completions for your IED
    """
    # Example for a real IED - replace with your actual IED name and path
    # Typical format: IEDName::LogicalDevice/LogicalNode.DataObject
    ied_control = 'SIEMENS_IED::simpleIOGenericIO/CSWI1.Pos'
    
    # Read current state first
    current_state = ctx.get(f'{ied_control}.stVal', None)
    ctx.log('info', f'Current breaker state: {current_state}')
    
    # Toggle the breaker
    new_state = not bool(current_state)
    success = ctx.send_command(ied_control, new_state)
    
    if success:
        ctx.log('info', f'Breaker toggled to {new_state}')
        
        # Wait and read new state
        ctx.sleep(0.5)
        updated_state = ctx.read(f'{ied_control}.stVal')
        ctx.log('info', f'Updated breaker state: {updated_state}')
    
    return success


# ============================================================================
# Example 5: Simulated IED Control
# ============================================================================
def example_simulated_ied_control(ctx):
    """
    Control a simulated IED created in SCADA Scout.
    
    Prerequisites:
    1. Create a simulated IED: Tools > Simulate IED
    2. Load an ICD/SCL file that includes control points
    3. The simulator will create controllable objects
    """
    # Replace with your simulated IED name
    sim_control = 'SimulatedIED::simpleIOGenericIO/CSWI1.Pos'
    
    # Pulse the breaker (close, wait, open)
    ctx.log('info', 'Starting breaker pulse sequence')
    
    # Close
    if ctx.send_command(sim_control, True):
        ctx.log('info', '  ✓ Breaker closed')
        ctx.sleep(2.0)
        
        # Open
        if ctx.send_command(sim_control, False):
            ctx.log('info', '  ✓ Breaker opened')
            return True
    
    ctx.log('error', 'Pulse sequence failed')
    return False


# ============================================================================
# Example 6: Continuous Monitoring and Control
# ============================================================================
def tick(ctx):
    """
    Continuous script that monitors a value and controls a breaker.
    This runs repeatedly at the interval you specify in the UI.
    """
    # Monitor a value (e.g., current)
    current_tag = 'IED1::simpleIOGenericIO/MMXU1.A.phsA.instMag'
    current_value = ctx.get(current_tag, 0.0)
    
    # Control point
    breaker_control = 'IED1::simpleIOGenericIO/CSWI1.Pos'
    breaker_state = ctx.get(f'{breaker_control}.stVal', False)
    
    # Simple logic: if current exceeds threshold and breaker is closed, open it
    threshold = 100.0
    if current_value > threshold and breaker_state:
        ctx.log('warning', f'Current {current_value} exceeds threshold {threshold}')
        ctx.log('warning', 'Opening breaker...')
        
        success = ctx.send_command(breaker_control, False)
        if success:
            ctx.log('info', 'Breaker opened successfully')
        else:
            ctx.log('error', 'Failed to open breaker!')


# ============================================================================
# Example 7: One-Shot Control Script
# ============================================================================
def main(ctx):
    """
    One-shot script that runs once when you click 'Run Once'.
    Good for testing or manual operations.
    """
    ctx.log('info', '=== Starting One-Shot Control Test ===')
    
    # Replace with your control point
    control_point = 'IED1::simpleIOGenericIO/CSWI1.Pos'
    
    # Read current state
    current = ctx.get(f'{control_point}.stVal', None)
    ctx.log('info', f'Current state: {current}')
    
    # Close breaker
    ctx.log('info', 'Sending CLOSE command...')
    success = ctx.send_command(control_point, True)
    
    if success:
        ctx.log('info', 'Command succeeded!')
        ctx.sleep(2.0)
        
        # Read new state
        new_state = ctx.read(f'{control_point}.stVal')
        ctx.log('info', f'New state: {new_state}')
    else:
        ctx.log('error', 'Command failed!')
    
    ctx.log('info', '=== Test Complete ===')


# ============================================================================
# Example 8: Error Handling and Retry Logic
# ============================================================================
def example_with_retry(ctx):
    """Control with automatic retry on failure."""
    control_point = 'IED1::simpleIOGenericIO/CSWI1.Pos'
    max_retries = 3
    retry_delay = 1.0  # seconds
    
    for attempt in range(max_retries):
        ctx.log('info', f'Control attempt {attempt + 1}/{max_retries}')
        
        success = ctx.send_command(control_point, True)
        
        if success:
            ctx.log('info', 'Control succeeded')
            return True
        else:
            ctx.log('warning', f'Attempt {attempt + 1} failed')
            if attempt < max_retries - 1:
                ctx.log('info', f'Retrying in {retry_delay}s...')
                ctx.sleep(retry_delay)
    
    ctx.log('error', f'All {max_retries} attempts failed')
    return False


# ============================================================================
# How to Use These Examples:
# ============================================================================
# 1. Open SCADA Scout
# 2. Go to Tools > Python Scripts
# 3. Copy one of the examples above into the editor
# 4. Replace device names and addresses with your actual IED tags
#    (Press Ctrl+Space to see available tags)
# 5. Click "Run Once" to test, or "Start Continuous" to run repeatedly
# 6. Monitor the Event Log to see command results and SBO workflow details
# ============================================================================
