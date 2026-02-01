"""
Example: Voltage Monitor with Debugging
Demonstrates using the Script IDE debugger to diagnose issues.

This script monitors voltage from an IED and logs warnings when out of range.
Use breakpoints and step-through debugging to see how it works.
"""

# Configuration
DEVICE_NAME = "IED1"
VOLTAGE_TAG = "simpleIOGenericIO/MMXU1.PhV.phsA.cVal.mag.f"
MIN_VOLTAGE = 220.0
MAX_VOLTAGE = 240.0
NOMINAL_VOLTAGE = 230.0

# State tracking
voltage_readings = []
alarm_active = False
alarm_count = 0


def check_voltage_range(voltage):
    """
    Check if voltage is within acceptable range.
    
    Set a breakpoint here to inspect the voltage value during debugging.
    """
    if voltage < MIN_VOLTAGE:
        return "LOW"
    elif voltage > MAX_VOLTAGE:
        return "HIGH"
    else:
        return "OK"


def update_statistics(voltage):
    """
    Track voltage statistics.
    
    Add voltage to history for debugging purposes.
    """
    global voltage_readings
    
    voltage_readings.append(voltage)
    
    # Keep only last 10 readings
    if len(voltage_readings) > 10:
        voltage_readings.pop(0)
    
    # Calculate average (good point for a breakpoint!)
    if voltage_readings:
        average = sum(voltage_readings) / len(voltage_readings)
        return average
    return 0


def handle_alarm(ctx, status, voltage):
    """
    Handle voltage alarms.
    
    Step through this function to see alarm logic.
    """
    global alarm_active, alarm_count
    
    if status != "OK" and not alarm_active:
        # New alarm condition
        alarm_active = True
        alarm_count += 1
        ctx.log('warning', f'Voltage {status}: {voltage:.2f}V (alarm #{alarm_count})')
        
        # You could write to an alarm register here
        # ctx.set('AlarmDevice::alarm_register', 1)
        
    elif status == "OK" and alarm_active:
        # Alarm cleared
        alarm_active = False
        ctx.log('info', f'Voltage returned to normal: {voltage:.2f}V')
        
        # Clear alarm register
        # ctx.set('AlarmDevice::alarm_register', 0)


def tick(ctx):
    """
    Main execution loop - called repeatedly.
    
    Try these debugging techniques:
    1. Set a breakpoint on the ctx.get() line
    2. Step Over (F10) to execute line by line
    3. Use Watch panel to monitor 'voltage' variable
    4. Check Variables tab to see alarm_active state
    """
    # Read voltage from device
    # Set breakpoint here and inspect tag address
    full_tag = f"{DEVICE_NAME}::{VOLTAGE_TAG}"
    voltage = ctx.get(full_tag, NOMINAL_VOLTAGE)
    
    # Check if we got a valid reading
    if voltage == 0:
        ctx.log('warning', f'No voltage reading from {DEVICE_NAME}')
        return
    
    # Update statistics
    # Step Into (F11) this function to see how average is calculated
    average = update_statistics(voltage)
    
    # Check voltage range
    # Step Into (F11) to see range checking logic
    status = check_voltage_range(voltage)
    
    # Handle alarms
    # Set breakpoint here to debug alarm logic
    handle_alarm(ctx, status, voltage)
    
    # Log current state (normal operation)
    if status == "OK":
        ctx.log('info', f'Voltage: {voltage:.2f}V (avg: {average:.2f}V)')


def main(ctx):
    """
    One-time initialization.
    Called once when script starts.
    """
    ctx.log('info', '=== Voltage Monitor Started ===')
    ctx.log('info', f'Monitoring: {DEVICE_NAME}::{VOLTAGE_TAG}')
    ctx.log('info', f'Range: {MIN_VOLTAGE}V - {MAX_VOLTAGE}V')
    
    # Check if device exists
    tags = ctx.list_tags(DEVICE_NAME)
    if not tags:
        ctx.log('error', f'Device {DEVICE_NAME} not found or not connected')
        ctx.log('info', 'Available devices:')
        all_tags = ctx.list_tags()
        devices = set(tag.split('::')[0] for tag in all_tags)
        for device in sorted(devices):
            ctx.log('info', f'  - {device}')
        return False
    
    ctx.log('info', f'Found {len(tags)} signals on {DEVICE_NAME}')
    ctx.log('info', 'Use Script IDE debugger to step through code')
    return True


# Debugging Tips:
# 
# 1. Run in Debug Mode (F9):
#    - Set breakpoints by clicking line numbers
#    - Red circles indicate active breakpoints
#
# 2. Execution Controls:
#    - F10: Step Over (execute current line)
#    - F11: Step Into (enter functions)
#    - Shift+F11: Step Out (exit current function)
#    - F8: Continue (run to next breakpoint)
#
# 3. Inspect State:
#    - Variables tab: See all local variables
#    - Watch tab: Monitor specific expressions
#    - Stack tab: View call hierarchy
#
# 4. Try These Exercises:
#    - Set breakpoint in check_voltage_range()
#    - Add watch expression: voltage > MAX_VOLTAGE
#    - Step through handle_alarm() when alarm triggers
#    - Inspect voltage_readings list in Variables tab
#
# 5. Modify and Test:
#    - Change MIN/MAX_VOLTAGE values
#    - Add new alarm conditions
#    - Track additional statistics
#    - Write alarms to Modbus registers
