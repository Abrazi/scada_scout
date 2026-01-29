"""Generator Simulation Controller for SCADA Scout
Python conversion template from GenRun_Edited.js (Triangle MicroWorks DTM Insight)

NOTE: This is a SIMPLIFIED TEMPLATE demonstrating the structure for a generator
simulation script in SCADA Scout. The original JavaScript is 1367 lines with complex
state machines, switchgear coordination, and extensive SSL (Signal Status Logic).

A full conversion would require:
1. Converting all GeneratorController and SwitchgearController classes
2. Implementing the state machine logic (STANDSTILL, STARTING, RUNNING, SHUTDOWN, FAULT)
3. Implementing ramping logic for voltage, frequency, and power
4. Implementing SSL (Signal Status Logic) flags for all 100+ control signals
5. Implementing load sharing between generators via switchgear controllers
6. Converting all Modbus register read/write operations to SCADA Scout API

For production use, you would need to:
- Complete the state machine implementation
- Add all SSL flag logic from the original
- Implement proper error handling and fault simulation
- Add switchgear coordination logic
- Test thoroughly with your Modbus devices

Usage:
- This runs continuously via tick(ctx) function
- Configure GENERATOR_IDS and SWITCHGEAR_IDS before running
- The script will read commands from Modbus registers and write simulated values
"""

import math
import time
from typing import Dict, List, Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

# Generator IDs to simulate (must match device names in DeviceManager)
GENERATOR_IDS = ["G1", "G2", "G3"]  # Add more as needed: G4, G5, ... G22

# Switchgear IDs (must match device names in DeviceManager)
SWITCHGEAR_IDS = ["GPS1", "GPS2", "GPS3", "GPS4"]

# Simulation update rate (seconds)
UPDATE_INTERVAL = 0.1  # 100ms like original

# Verbosity level (0=off, 1=general, 2=state changes, 3=modbus, 4=variables, 5=detailed)
VERBOSE = 2

# ============================================================================
# STATE CONSTANTS (from original JavaScript)
# ============================================================================

STATE_STANDSTILL = 0
STATE_STARTING = 1
STATE_RUNNING = 2
STATE_SHUTDOWN = 3
STATE_FAULT = 4
STATE_FAST_TRANSFER = 5

STATE_NAMES = ["standstill", "starting", "running", "shutdown", "fault", "fastTransfer"]

CONTROL_MANUAL = -1
CONTROL_AUTO = 1

# ============================================================================
# GENERATOR CONTROLLER CLASS
# ============================================================================

class GeneratorController:
    """Simulates a single generator's behavior with state machine control.
    
    This is a simplified version. The original has:
    - 100+ SSL (Signal Status Logic) flags
    - Complex voltage/frequency/power ramping
    - Fault injection and handling
    - Load sharing coordination
    - Fast transfer logic
    """
    
    def __init__(self, gen_id: str):
        self.id = gen_id
        self.last_update_time = time.time()
        
        # State machine
        self.state = STATE_STANDSTILL
        self.last_state = STATE_STANDSTILL
        
        # Design parameters
        self.de_excited_voltage = 3500.0  # V
        self.excited_voltage = 10500.0    # V
        self.nominal_frequency = 50.0     # Hz
        self.nominal_power = 3500.0       # kW
        
        # Ramp rates (per second)
        self.ramp_rate_voltage = 10000.0    # V/s
        self.ramp_rate_frequency = 200.0    # Hz/s
        self.ramp_rate_power_up = 10000.0   # kW/s
        self.ramp_rate_power_down = 10000.0 # kW/s
        
        # Timers
        self.start_delay = 0.1  # seconds
        self.stop_delay = 0.1   # seconds
        self.start_timer = 0.0
        self.stop_timer = 0.0
        
        # Simulated outputs
        self.simulated_voltage = 0.0      # V
        self.simulated_frequency = 0.0    # Hz
        self.simulated_current = 0.0      # A
        self.simulated_active_power = 0.0 # kW
        self.simulated_reactive_power = 0.0  # kVAr
        
        # Setpoints (from Modbus commands)
        self.setpoint_power = 0.0
        self.setpoint_reactive_power = 0.0
        
        # Control flags (simplified - original has 100+)
        self.demand_signal = False
        self.excite_signal = False
        self.deexcite_signal = False
        self.is_deexcited = False
        
    def update(self, dt: float, ctx):
        """Main update loop - called every cycle.
        
        Args:
            dt: Time delta since last update (seconds)
            ctx: ScriptContext for reading/writing tags
        """
        # Read commands from Modbus registers
        self._read_commands(ctx)
        
        # State machine logic
        self._update_state_machine(dt, ctx)
        
        # Ramp simulated values
        self._update_simulated_values(dt, ctx)
        
        # Write simulated values to Modbus registers
        self._write_outputs(ctx)
        
    def _read_commands(self, ctx):
        """Read command signals from Modbus registers.
        
        Example register mapping (adjust based on Gen_Registers.csv):
        - R000: Demand signal (bool)
        - R001: Excite signal (bool)
        - R002: Deexcite signal (bool)
        - R010: Setpoint power (kW)
        - R011: Setpoint reactive power (kVAr)
        """
        # Example: read demand signal from holding register 40000
        self.demand_signal = bool(ctx.get(f'{self.id}::1:3:40000', 0))
        self.excite_signal = bool(ctx.get(f'{self.id}::1:3:40001', 0))
        self.deexcite_signal = bool(ctx.get(f'{self.id}::1:3:40002', 0))
        
        # Read setpoints (holding registers 40010, 40011)
        self.setpoint_power = float(ctx.get(f'{self.id}::1:3:40010', 0))
        self.setpoint_reactive_power = float(ctx.get(f'{self.id}::1:3:40011', 0))
        
    def _update_state_machine(self, dt: float, ctx):
        """Update generator state machine."""
        old_state = self.state
        
        if self.state == STATE_STANDSTILL:
            if self.demand_signal and self.excite_signal:
                self.state = STATE_STARTING
                self.start_timer = 0.0
                if VERBOSE >= 2:
                    ctx.log('info', f'{self.id}: STANDSTILL -> STARTING')
                    
        elif self.state == STATE_STARTING:
            self.start_timer += dt
            if self.start_timer >= self.start_delay:
                self.state = STATE_RUNNING
                if VERBOSE >= 2:
                    ctx.log('info', f'{self.id}: STARTING -> RUNNING')
                    
        elif self.state == STATE_RUNNING:
            if not self.demand_signal or self.deexcite_signal:
                self.state = STATE_SHUTDOWN
                self.stop_timer = 0.0
                if VERBOSE >= 2:
                    ctx.log('info', f'{self.id}: RUNNING -> SHUTDOWN')
                    
        elif self.state == STATE_SHUTDOWN:
            self.stop_timer += dt
            if self.stop_timer >= self.stop_delay:
                self.state = STATE_STANDSTILL
                if VERBOSE >= 2:
                    ctx.log('info', f'{self.id}: SHUTDOWN -> STANDSTILL')
        
        self.last_state = old_state
        
    def _update_simulated_values(self, dt: float, ctx):
        """Ramp voltage, frequency, power based on current state."""
        
        # Voltage ramping
        target_voltage = 0.0
        if self.state in [STATE_STARTING, STATE_RUNNING]:
            target_voltage = self.excited_voltage
        else:
            target_voltage = 0.0
            
        if self.simulated_voltage < target_voltage:
            self.simulated_voltage += self.ramp_rate_voltage * dt
            self.simulated_voltage = min(self.simulated_voltage, target_voltage)
        elif self.simulated_voltage > target_voltage:
            self.simulated_voltage -= self.ramp_rate_voltage * dt
            self.simulated_voltage = max(self.simulated_voltage, target_voltage)
            
        # Frequency ramping
        target_frequency = self.nominal_frequency if self.state == STATE_RUNNING else 0.0
        if self.simulated_frequency < target_frequency:
            self.simulated_frequency += self.ramp_rate_frequency * dt
            self.simulated_frequency = min(self.simulated_frequency, target_frequency)
        elif self.simulated_frequency > target_frequency:
            self.simulated_frequency -= self.ramp_rate_frequency * dt
            self.simulated_frequency = max(self.simulated_frequency, target_frequency)
            
        # Power ramping (only when running)
        if self.state == STATE_RUNNING:
            if self.simulated_active_power < self.setpoint_power:
                self.simulated_active_power += self.ramp_rate_power_up * dt
                self.simulated_active_power = min(self.simulated_active_power, self.setpoint_power)
            elif self.simulated_active_power > self.setpoint_power:
                self.simulated_active_power -= self.ramp_rate_power_down * dt
                self.simulated_active_power = max(self.simulated_active_power, self.setpoint_power)
        else:
            # Ramp down to zero when not running
            if self.simulated_active_power > 0:
                self.simulated_active_power -= self.ramp_rate_power_down * dt
                self.simulated_active_power = max(self.simulated_active_power, 0.0)
                
        # Simple current calculation (P = V * I)
        if self.simulated_voltage > 100:
            self.simulated_current = (self.simulated_active_power * 1000) / self.simulated_voltage
        else:
            self.simulated_current = 0.0
            
    def _write_outputs(self, ctx):
        """Write simulated values to Modbus output registers.
        
        Example output register mapping (adjust based on your needs):
        - R100: State (int)
        - R101: Voltage (V)
        - R102: Frequency (Hz)
        - R103: Active Power (kW)
        - R104: Reactive Power (kVAr)
        - R105: Current (A)
        """
        ctx.set(f'{self.id}::1:3:40100', int(self.state))
        ctx.set(f'{self.id}::1:3:40101', int(self.simulated_voltage))
        ctx.set(f'{self.id}::1:3:40102', int(self.simulated_frequency * 10))  # 0.1 Hz resolution
        ctx.set(f'{self.id}::1:3:40103', int(self.simulated_active_power))
        ctx.set(f'{self.id}::1:3:40104', int(self.simulated_reactive_power))
        ctx.set(f'{self.id}::1:3:40105', int(self.simulated_current))
        
        if VERBOSE >= 3:
            ctx.log('info', f'{self.id}: V={self.simulated_voltage:.0f}V F={self.simulated_frequency:.1f}Hz P={self.simulated_active_power:.0f}kW')


# ============================================================================
# SWITCHGEAR CONTROLLER CLASS
# ============================================================================

class SwitchgearController:
    """Manages load sharing between generators assigned to this switchgear.
    
    Original has complex load distribution, fast transfer, and bus monitoring.
    This is a simplified placeholder.
    """
    
    def __init__(self, swg_id: str):
        self.id = swg_id
        self.assigned_generators: List[GeneratorController] = []
        
    def update(self, dt: float, ctx):
        """Update switchgear logic and distribute load."""
        # TODO: Implement load sharing logic
        # Original distributes total load demand among online generators
        pass


# ============================================================================
# GLOBAL STATE
# ============================================================================

# Generator and switchgear controller instances
_generators: Dict[str, GeneratorController] = {}
_switchgears: Dict[str, SwitchgearController] = {}
_last_tick_time = None


def _initialize_controllers(ctx):
    """Initialize generator and switchgear controllers."""
    global _generators, _switchgears
    
    # Create generator controllers
    for gen_id in GENERATOR_IDS:
        if gen_id not in _generators:
            _generators[gen_id] = GeneratorController(gen_id)
            ctx.log('info', f'Initialized controller for {gen_id}')
    
    # Create switchgear controllers
    for swg_id in SWITCHGEAR_IDS:
        if swg_id not in _switchgears:
            _switchgears[swg_id] = SwitchgearController(swg_id)
            ctx.log('info', f'Initialized controller for {swg_id}')


def tick(ctx):
    """Main continuous execution loop - called repeatedly by SCADA Scout.
    
    This function runs at the interval specified in user_scripts.json.
    """
    global _last_tick_time
    
    # Initialize on first run
    if not _generators:
        _initialize_controllers(ctx)
        ctx.log('info', '=== Generator Simulation Started ===')
        ctx.log('info', f'Simulating {len(GENERATOR_IDS)} generators and {len(SWITCHGEAR_IDS)} switchgears')
    
    # Calculate time delta
    current_time = time.time()
    if _last_tick_time is None:
        dt = UPDATE_INTERVAL
    else:
        dt = current_time - _last_tick_time
    _last_tick_time = current_time
    
    # Update all generators
    for gen in _generators.values():
        try:
            gen.update(dt, ctx)
        except Exception as e:
            ctx.log('error', f'Error updating {gen.id}: {str(e)}')
    
    # Update all switchgears
    for swg in _switchgears.values():
        try:
            swg.update(dt, ctx)
        except Exception as e:
            ctx.log('error', f'Error updating {swg.id}: {str(e)}')


# For one-shot initialization (run once to set up)
def main(ctx):
    """One-shot initialization - adds devices if needed."""
    ctx.log('info', 'Generator simulation script loaded')
    ctx.log('info', f'Will simulate: {", ".join(GENERATOR_IDS)}')
    ctx.log('info', 'To run continuously, enable this script with tick() function')
    return "Ready - enable continuous execution to start simulation"
