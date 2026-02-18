import logging
import threading
import time
import math
from typing import Optional, List, Dict
from enum import IntEnum
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext
import asyncio

logger = logging.getLogger(__name__)

# Verbosity and log level control
# Set VERBOSE=True for DEBUG level; HEARTBEAT_LOG_LEVEL controls heartbeat (R192 bit 7) logging
VERBOSE = False  # Toggle for more verbose logging (DEBUG)
HEARTBEAT_LOG_LEVEL =  25 # Custom level between INFO(20) and WARNING(30) regular info() calls will stay at 20 (INFO), and only logs specifically using the level 25 will say HEARTBEAT.
logging.addLevelName(HEARTBEAT_LOG_LEVEL, "HEARTBEAT")
LOG_LEVEL = logging.DEBUG if VERBOSE else logging.INFO
logger.setLevel(LOG_LEVEL)
# Ensure root logger respects our chosen level as well
logging.getLogger().setLevel(LOG_LEVEL)

VOLTAGE_EPSILON = 10
FREQUENCY_EPSILON = 0.1
POWER_EPSILON = 10

# IP address mappings
GEN_IP_MAP = {
    "G1": "172.16.31.13", "G2": "172.16.31.23", "G3": "172.16.31.33", "G4": "172.16.31.43", "G5": "172.16.31.53",
    "G6": "172.16.32.13", "G7": "172.16.32.23", "G8": "172.16.32.33", "G9": "172.16.32.43", "G10": "172.16.32.53",
    "G11": "172.16.33.13", "G12": "172.16.33.23", "G13": "172.16.33.33", "G14": "172.16.33.43", "G15": "172.16.33.53",
    "G16": "172.16.34.13", "G17": "172.16.34.23", "G18": "172.16.34.33", "G19": "172.16.34.43", "G20": "172.16.34.53",
    "G21": "172.16.35.13", "G22": "172.16.35.23"
}

SWG_IP_MAP = {
    "GPS1": "172.16.31.63", "GPS2": "172.16.32.63", "GPS3": "172.16.33.63", "GPS4": "172.16.34.63"
}


class GeneratorState(IntEnum):
    STANDSTILL = 0
    STARTING = 1
    RUNNING = 2
    SHUTDOWN = 3
    FAULT = 4
    FAST_TRANSFER = 5


# State machine string to enum mapping
STATE_MAP = {
    "standstill": GeneratorState.STANDSTILL,
    "starting": GeneratorState.STARTING,
    "running": GeneratorState.RUNNING,
    "shutdown": GeneratorState.SHUTDOWN,
    "fault": GeneratorState.FAULT,
    "fastTransfer": GeneratorState.FAST_TRANSFER,
}


class StateMachine:
    def __init__(self, initial_state: str):
        self.state = initial_state
        self.transitions: Dict[str, Dict[str, str]] = {}
        self.ignored_triggers: Dict[str, List[str]] = {}

    def add_transition(self, from_state: str, trigger: str, to_state: str):
        self.transitions.setdefault(from_state, {})[trigger] = to_state

    def add_ignore(self, state: str, trigger: str):
        self.ignored_triggers.setdefault(state, []).append(trigger)

    def fire(self, trigger: str) -> bool:
        if trigger in self.ignored_triggers.get(self.state, []):
            return False
        nxt = self.transitions.get(self.state, {}).get(trigger)
        if nxt:
            self.state = nxt
            return True
        return False


class GeneratorController:
    def __init__(self, gen_id: str, register_base: int, ip_address: str = ""):
        if not gen_id:
            raise ValueError("Invalid generator ID")
        self.id = gen_id
        self.register_base = register_base
        self.ip_address = ip_address
        self.last_processed_state = None

        self.DeExcitedVoltage = 3500.0
        self.ExcitedVoltage = 10500.0
        self.rVoltage = 0.0

        self.NominalFrequency = 50.0
        self.NominalPower = 3500.0
        # Fix: Add separate reactive power rating (typically ~0.4-0.6 of active power rating)
        self.NominalReactivePower = 2100.0  # Typical for 0.8-0.85 power factor

        self.RampRateVoltage = 10000.0
        self.RampRateFrequency = 200.0
        self.RampRatePowerUp = 10000.0
        self.RampRatePowerDown = 10000.0

        self.dt = 100
        self.StartDelay = 100
        self.StopDelay = 100
        self.startTimer = 0
        self.stopTimer = 1
        self.deadBusWindowTimer = 0
        self.ssl710PreviousValue = False

        self.state = GeneratorState.STANDSTILL
        self.faultDetected = False

        self.SimulateFailToStart = False
        self.FailRampUp = False
        self.FailRampDown = False
        self.FailStartTime = False

        self.SimulatedVoltage = 0.0
        self.SimulatedFrequency = 0.0
        self.SimulatedCurrent = 0.0
        self.SimulatedActivePower = 0.0
        self.SimulatedReactivePower = 0.0

        self.rSetpointPower = 0.0
        self.rSetpointReactivePower = 0.0
        self.previousSetpointPower = 0.0
        self.previousSetpointReactivePower = 0.0

        self.FCB1 = True
        self.FCB2 = False
        self.previousR192 = 0  # Track R192 to detect actual changes
        self.last_heartbeat_time = time.time()
        self.heartbeat_failed = False
        self.HEARTBEAT_TIMEOUT = 10.0 #10 seconds

        self.SSL = {
            'SSL425_ServiceSWOff': False,
            'SSL426_ServiceSWManual': False,
            'SSL427_ServiceSWAuto': True,
            'SSL429_GenCBClosed': False,
            'SSL430_GenCBOpen': True,
            'SSL431_OperOn': False,
            'SSL432_OperOff': True,
            'SSL435_MainsCBClosed': False,
            'SSL437_TurboChUnitGeneralTrip': False,
            'SSL438_TurboChUnitGeneralWarn': False,
            'SSL439_IgnSysGeneralTrip': False,
            'SSL440_IgnSysGeneralWarn': False,
            'SSL441_SyncGenActivated': False,
            'SSL443_EngineInStartingPhase': False,
            'SSL444_ReadyforAutoDem': True,
            'SSL445_DemandforAux': False,
            'SSL448_ModuleisDemanded': False,
            'SSL449_OperEngineisRunning': False,
            'SSL452_GeneralTrip': False,
            'SSL453_GeneralWarn': False,
            'SSL545_UtilityOperModuleBlocked': False,
            'SSL546_GenBreakerOpenFail': False,
            'SSL547_GenDeexcited': False,
            'SSL548_PowerReductionActivated': False,
            'SSL549_LoadRejectedGCBOpen': False,
            'SSL550_GenSyncLoadReleas': False,
            'SSL563_ReadyforFastStart': False,
            'SSL564_ModuleLockedOut': False,
            'SSL592_EngineAtStandStill': True,
            'SSL593_ScaveningInOper': False,
            'SSL3612_EmergStopPBEngRoom': False,
            'SSL3613_EmergStopPBEngVentRoom': False,
            'SSL3614_EmergStopPBLVMVCtrlRoom': False,
            'SSL3615_EmergStopPBExtCustom': False,
            'SSL3616_AuxSupplySource1': False,
            'SSL3617_AuxSupplySource2': False,
            'SSL3624_TrAppPowExceeded': False,
            'SSL3625_EngSmoothLoadRejectStart': False,
            'SSL3626_LoadRejWaitforReleaseSync': False,
            'SSL3627_GenAntiCondensHeatInOper': False,
            'SSL3630_ReleaseLoadAfterGenExcit': False,
            'SSL701_DemandModule_CMD': False,
            'SSL702_UtilityOperModuleBlocked_CMD': False,
            'SSL703_MainsCBClosed_CMD': False,
            'SSL704_EnGenBreakerActToDeadBus_CMD': False,
            'SSL705_LoadRejectGenCBOpen_CMD': False,
            'SSL706_AuxPowSuppSource1_CMD': False,
            'SSL707_AuxPowSuppSource2_CMD': False,
            'SSL708_ClockPulse_CMD': False,
            'SSL709_GenExcitationOff_CMD': False,
            'SSL710_OthGCBClosedandExcitOn_CMD': False
        }

        self.sm = StateMachine("standstill")
        self.sm.add_transition("standstill", "demand", "starting")
        self.sm.add_transition("standstill", "faultDetected", "fault")
        self.sm.add_ignore("starting", "voltageReady")
        self.sm.add_ignore("starting", "freqReady")
        self.sm.add_transition("starting", "startComplete", "running")
        self.sm.add_transition("starting", "shutdown", "shutdown")
        self.sm.add_transition("starting", "faultDetected", "fault")
        self.sm.add_transition("running", "shutdown", "shutdown")
        self.sm.add_transition("running", "transfer", "fastTransfer")
        self.sm.add_transition("running", "faultDetected", "fault")
        self.sm.add_transition("shutdown", "powerZero", "standstill")
        self.sm.add_transition("shutdown", "faultDetected", "fault")
        self.sm.add_transition("fault", "faultCleared", "standstill")
        self.sm.add_transition("fault", "shutdown", "shutdown")
        self.sm.add_transition("fastTransfer", "demand", "running")
        self.sm.add_transition("fastTransfer", "shutdown", "shutdown")
        self.sm.add_transition("fastTransfer", "faultDetected", "fault")

        self.lock = threading.Lock()
        self._last_status_log = None
        self._last_event_log = None

    def log(self, message: str):
        """Log generator events - uses INFO level for state transitions and important events"""
        log_msg = f"[{self.id}] [{self.sm.state}] {message}"
        if log_msg != self._last_event_log:
            logger.info(log_msg)
            self._last_event_log = log_msg

    def ramp(self, value: float, target: float, rate: float, fail_flag: bool, param_type: str) -> float:
        if fail_flag:
            return value
        # Improved ramp logic - more readable and symmetric
        delta = target - value
        max_step = rate * self.dt / 1000.0
        step = max(min(delta, max_step), -max_step)
        new_value = value + step
        
        # Apply parameter-specific limits
        if param_type == 'power':
            return min(max(new_value, 0), self.NominalPower)
        if param_type == 'reactive_power':
            # Fix: Use proper reactive power limit
            return min(max(new_value, -self.NominalReactivePower), self.NominalReactivePower)
        if param_type == 'voltage':
            return min(max(new_value, 0), self.ExcitedVoltage)
        if param_type == 'frequency':
            return min(max(new_value, 0), self.NominalFrequency * 1.1)
        return new_value

    def parse_R192(self, value: int):
        flags = [
            ('SSL701_DemandModule_CMD', 0),
            ('SSL702_UtilityOperModuleBlocked_CMD', 1),
            ('SSL703_MainsCBClosed_CMD', 2),
            ('SSL704_EnGenBreakerActToDeadBus_CMD', 3),
            ('SSL705_LoadRejectGenCBOpen_CMD', 4),
            ('SSL706_AuxPowSuppSource1_CMD', 5),
            ('SSL707_AuxPowSuppSource2_CMD', 6),
            ('SSL708_ClockPulse_CMD', 7), #Heartbeat
            ('SSL709_GenExcitationOff_CMD', 8),
            ('SSL710_OthGCBClosedandExcitOn_CMD', 9)
        ]
        for name, bit in flags:
            self.SSL[name] = ((value >> bit) & 1) == 1

    def reset_outputs(self):
        self.SimulatedVoltage = 0.0
        self.SimulatedFrequency = 0.0
        self.SimulatedCurrent = 0.0
        self.SimulatedActivePower = 0.0
        self.SimulatedReactivePower = 0.0
        self.rVoltage = 0.0
        self.SSL['SSL429_GenCBClosed'] = False
        self.SSL['SSL430_GenCBOpen'] = True
        self.SSL['SSL431_OperOn'] = False
        self.SSL['SSL432_OperOff'] = True
        self.SSL['SSL444_ReadyforAutoDem'] = True
        self.SSL['SSL448_ModuleisDemanded'] = False
        self.SSL['SSL547_GenDeexcited'] = False
        self.SSL['SSL592_EngineAtStandStill'] = True
        self.SSL['SSL550_GenSyncLoadReleas'] = False

    def on_enter_standstill(self):
        self.log("ENTERING STATE: Standstill")
        self.reset_outputs()

    def on_enter_starting(self):
        self.log("ENTERING STATE: Starting")
        self.startTimer = 0
        self.SSL['SSL431_OperOn'] = True
        self.SSL['SSL432_OperOff'] = False
        self.SSL['SSL448_ModuleisDemanded'] = True
        self.SSL['SSL592_EngineAtStandStill'] = False
        self.SSL['SSL443_EngineInStartingPhase'] = True

    def on_enter_running(self):
        self.log("ENTERING STATE: Running")
        self.SSL['SSL550_GenSyncLoadReleas'] = True
        self.SSL['SSL547_GenDeexcited'] = True
        self.SSL['SSL448_ModuleisDemanded'] = True
        self.SSL['SSL444_ReadyforAutoDem'] = False
        self.SSL['SSL449_OperEngineisRunning'] = True
        self.SSL['SSL592_EngineAtStandStill'] = False
        self.SSL['SSL443_EngineInStartingPhase'] = False

    def on_enter_shutdown(self):
        self.log("ENTERING STATE: Shutdown")
        self.stopTimer = 0
        self.SSL['SSL448_ModuleisDemanded'] = False

    def on_enter_fault(self):
        self.log("ENTERING STATE: Fault")
        self.reset_outputs()
        # Fix: Explicitly clear engine running flag in fault state
        self.SSL['SSL449_OperEngineisRunning'] = False

    def on_enter_fast_transfer(self):
        self.log("ENTERING STATE: FastTransfer")
        self.SSL['SSL429_GenCBClosed'] = False
        self.SSL['SSL430_GenCBOpen'] = True
        self.SimulatedFrequency = self.NominalFrequency
        self.SimulatedVoltage = self.ExcitedVoltage
        self.SimulatedActivePower = 0
        self.SimulatedReactivePower = 0

    def update_state(self):
        if not self.SSL['SSL427_ServiceSWAuto']:
            return
        current_state = self.sm.state
        if current_state != self.last_processed_state:
            self.log(f"STATE TRANSITION: {self.last_processed_state} -> {current_state}")
            func_name = f"on_enter_{current_state}"
            if hasattr(self, func_name):
                getattr(self, func_name)()
            self.last_processed_state = current_state
            # Use safe mapping instead of direct enum lookup
            self.state = STATE_MAP.get(current_state, GeneratorState.STANDSTILL)
        if self.faultDetected and self.sm.state != "fault":
            self.sm.fire("faultDetected")
            return
        voltage_in_range = abs(self.SimulatedVoltage - self.rVoltage) < VOLTAGE_EPSILON
        frequency_in_range = abs(self.SimulatedFrequency - self.NominalFrequency) < FREQUENCY_EPSILON
        is_power_zero = abs(self.SimulatedActivePower) < POWER_EPSILON
        if self.sm.state == "starting":
            self.startTimer += self.dt
        elif self.sm.state == "shutdown":
            self.stopTimer += self.dt
        if self.sm.state == "standstill":
            if self.SSL['SSL701_DemandModule_CMD']:
                self.sm.fire("demand")
        elif self.sm.state == "starting":
            if not self.SSL['SSL701_DemandModule_CMD']:
                self.sm.fire("shutdown")
            else:
                if voltage_in_range:
                    self.sm.fire("voltageReady")
                if frequency_in_range:
                    self.sm.fire("freqReady")
                if (self.startTimer >= self.StartDelay or self.FailStartTime) and voltage_in_range and frequency_in_range:
                    # Fix: Check SimulateFailToStart flag - if true, block start completion
                    if self.SimulateFailToStart:
                        self.log("Start blocked by SimulateFailToStart flag")
                        # Don't proceed with close breaker or startComplete
                    else:
                        bus_is_live = self.SSL['SSL710_OthGCBClosedandExcitOn_CMD']
                        if self.SSL['SSL709_GenExcitationOff_CMD']:
                            self.SSL['SSL448_ModuleisDemanded'] = True
                            self.SSL['SSL547_GenDeexcited'] = True
                            self.SSL['SSL550_GenSyncLoadReleas'] = True
                        if self.SSL['SSL704_EnGenBreakerActToDeadBus_CMD'] and not bus_is_live and self.SSL['SSL430_GenCBOpen']:
                            self.SSL['SSL429_GenCBClosed'] = True
                            self.SSL['SSL430_GenCBOpen'] = False
                            self.SSL['SSL431_OperOn'] = True
                            self.SSL['SSL432_OperOff'] = False
                            self.log("CB CLOSED to dead busbar (SSL704)")
                            self.sm.fire("startComplete")
                        if bus_is_live and not self.SSL['SSL709_GenExcitationOff_CMD'] and self.SSL['SSL430_GenCBOpen']:
                            self.SSL['SSL441_SyncGenActivated'] = True
                            self.SSL['SSL547_GenDeexcited'] = False
                            self.SSL['SSL3630_ReleaseLoadAfterGenExcit'] = True
                            phase_angle_ok = True
                            if phase_angle_ok:
                                self.SSL['SSL429_GenCBClosed'] = True
                                self.SSL['SSL430_GenCBOpen'] = False
                                self.SSL['SSL431_OperOn'] = True
                                self.SSL['SSL432_OperOff'] = False
                                self.log("CB CLOSED via auto-sync to live busbar")
                                self.sm.fire("startComplete")
        elif self.sm.state == "running":
            if self.SSL['SSL705_LoadRejectGenCBOpen_CMD']:
                self.sm.fire("transfer")
            elif not self.SSL['SSL701_DemandModule_CMD']:
                self.sm.fire("shutdown")
        elif self.sm.state == "shutdown":
            power_below_10_percent = self.SimulatedActivePower < (self.NominalPower * 0.1)
            if power_below_10_percent and self.SSL['SSL429_GenCBClosed']:
                self.SSL['SSL429_GenCBClosed'] = False
                self.SSL['SSL430_GenCBOpen'] = True
                self.SSL['SSL448_ModuleisDemanded'] = False
                self.SSL['SSL431_OperOn'] = False
                self.SSL['SSL432_OperOff'] = True
                self.log(f"CB OPENED - power below 10% ({self.SimulatedActivePower:.1f} kW)")
            if is_power_zero and self.stopTimer >= self.StopDelay:
                self.log("Shutdown complete - transitioning to standstill")
                self.sm.fire("powerZero")
        elif self.sm.state == "fastTransfer":
            if self.SSL['SSL429_GenCBClosed']:
                self.SSL['SSL429_GenCBClosed'] = False
                self.SSL['SSL430_GenCBOpen'] = True
            if not self.SSL['SSL705_LoadRejectGenCBOpen_CMD']:
                self.SSL['SSL429_GenCBClosed'] = True
                self.SSL['SSL430_GenCBOpen'] = False
                self.sm.fire("demand")

    def validate_ssl_flags(self):
        service_modes = sum([self.SSL['SSL427_ServiceSWAuto'], self.SSL['SSL426_ServiceSWManual'], self.SSL['SSL425_ServiceSWOff']])
        if service_modes > 1:
            if self.SSL['SSL427_ServiceSWAuto']:
                self.SSL['SSL426_ServiceSWManual'] = False
                self.SSL['SSL425_ServiceSWOff'] = False
            elif self.SSL['SSL426_ServiceSWManual']:
                self.SSL['SSL427_ServiceSWAuto'] = False
                self.SSL['SSL425_ServiceSWOff'] = False
        elif service_modes == 0:
            self.SSL['SSL427_ServiceSWAuto'] = True
        if self.SSL['SSL430_GenCBOpen']:
            self.SSL['SSL429_GenCBClosed'] = False
        elif self.SSL['SSL429_GenCBClosed']:
            self.SSL['SSL430_GenCBOpen'] = False
        else:
            self.SSL['SSL430_GenCBOpen'] = True
        if self.SSL['SSL431_OperOn']:
            self.SSL['SSL432_OperOff'] = False
        elif self.SSL['SSL432_OperOff']:
            self.SSL['SSL431_OperOn'] = False
        if self.SSL['SSL592_EngineAtStandStill']:
            self.SSL['SSL449_OperEngineisRunning'] = False
            self.SSL['SSL443_EngineInStartingPhase'] = False
        # Fix: Removed SSL547_GenDeexcited override logic - state machine controls this
        # SSL709 is a command input, but excitation state is determined by state transitions
        if self.SSL['SSL705_LoadRejectGenCBOpen_CMD']:
            self.SSL['SSL549_LoadRejectedGCBOpen'] = True
        else:
            self.SSL['SSL549_LoadRejectedGCBOpen'] = False

    def update_simulation_dynamics(self):
        if self.sm.state in ('standstill', 'fault'):
            self.rVoltage = 0.0
        elif self.sm.state == 'starting':
            if self.SSL['SSL547_GenDeexcited']:
                self.rVoltage = self.DeExcitedVoltage
            else:
                if abs(self.SimulatedVoltage - self.DeExcitedVoltage) < VOLTAGE_EPSILON or self.SimulatedVoltage > self.DeExcitedVoltage:
                    self.rVoltage = self.ExcitedVoltage
                else:
                    self.rVoltage = self.DeExcitedVoltage
        elif self.sm.state == 'running':
            self.rVoltage = self.DeExcitedVoltage if self.SSL['SSL547_GenDeexcited'] else self.ExcitedVoltage
        elif self.sm.state == 'shutdown':
            self.rVoltage = 0.0
        elif self.sm.state == 'fastTransfer':
            self.rVoltage = self.ExcitedVoltage

        self.SimulatedVoltage = self.ramp(self.SimulatedVoltage, self.rVoltage, self.RampRateVoltage, self.FailRampUp, 'voltage')

        target_frequency = 0.0
        if self.sm.state in ['starting', 'running', 'fastTransfer']:
            target_frequency = self.NominalFrequency
        elif self.sm.state == 'shutdown':
            target_frequency = 0.0

        self.SimulatedFrequency = self.ramp(self.SimulatedFrequency, target_frequency, self.RampRateFrequency, self.FailRampUp, 'frequency')
        if self.sm.state in ['standstill', 'fault']:
            self.SimulatedFrequency = 0.0

        target_power = 0.0
        if self.sm.state == 'running' and self.SSL['SSL429_GenCBClosed']:
            target_power = self.rSetpointPower
        elif self.sm.state == 'fastTransfer':
            target_power = 0.0

        current_power_ramp_rate = self.RampRatePowerDown if (self.SimulatedActivePower > target_power and target_power == 0.0) else self.RampRatePowerUp
        fail_ramp_flag = self.FailRampDown if (self.SimulatedActivePower > target_power and target_power == 0.0) else self.FailRampUp
        if self.sm.state == 'shutdown':
            current_power_ramp_rate = self.RampRatePowerDown
            fail_ramp_flag = self.FailRampDown

        self.SimulatedActivePower = self.ramp(self.SimulatedActivePower, target_power, current_power_ramp_rate, fail_ramp_flag, 'power')
        if (self.SSL['SSL430_GenCBOpen'] and self.sm.state != 'starting') or self.sm.state in ['standstill', 'fault']:
            self.SimulatedActivePower = 0.0

        target_reactive_power = 0.0
        if self.sm.state == 'running' and self.SSL['SSL429_GenCBClosed']:
            target_reactive_power = self.rSetpointReactivePower
        elif self.sm.state == 'fastTransfer':
            target_reactive_power = 0.0

        current_reactive_power_ramp_rate = self.RampRatePowerDown if (self.SimulatedReactivePower > target_reactive_power and target_reactive_power == 0.0) else self.RampRatePowerUp
        fail_reactive_ramp_flag = self.FailRampDown if (self.SimulatedReactivePower > target_reactive_power and target_reactive_power == 0.0) else self.FailRampUp
        if self.sm.state == 'shutdown':
            current_reactive_power_ramp_rate = self.RampRatePowerDown
            fail_reactive_ramp_flag = self.FailRampDown

        self.SimulatedReactivePower = self.ramp(self.SimulatedReactivePower, target_reactive_power, current_reactive_power_ramp_rate, fail_reactive_ramp_flag, 'reactive_power')
        if (self.SSL['SSL430_GenCBOpen'] and self.sm.state != 'starting') or self.sm.state in ['standstill', 'fault']:
            self.SimulatedReactivePower = 0.0

        P_kW = self.SimulatedActivePower
        Q_kVAr = self.SimulatedReactivePower
        S_kVA = math.sqrt(P_kW * P_kW + Q_kVAr * Q_kVAr)
        if self.SimulatedVoltage > VOLTAGE_EPSILON:
            self.SimulatedCurrent = (S_kVA * 1000) / (self.SimulatedVoltage * 1.732)
        else:
            self.SimulatedCurrent = 0.0
        self.SimulatedCurrent = float(f"{self.SimulatedCurrent:.2f}")

    def tick(self, datastore: ModbusDeviceContext):
        status_line = (
            f"{self.id} | State: {self.sm.state} | "
            f"V={self.SimulatedVoltage:.1f} | "
            f"F={self.SimulatedFrequency:.1f} | "
            f"P={self.SimulatedActivePower:.1f} | "
            f"CB={self.SSL['SSL429_GenCBClosed']}"
        )
        if status_line != self._last_status_log:
            logger.info(status_line)
            self._last_status_log = status_line
        with self.lock:
            # Fix: Read inputs and update state BEFORE calculating simulation dynamics
            # This prevents 1-cycle lag where physics use previous state
            R095 = datastore.getValues(3, self.register_base + 95, count=1)
            if isinstance(R095, list):
                R095_Value = R095[0]
                self.SimulateFailToStart = ((R095_Value >> 0) & 1) == 1
                self.FailRampUp = ((R095_Value >> 1) & 1) == 1
                self.FailRampDown = ((R095_Value >> 2) & 1) == 1
                self.FailStartTime = ((R095_Value >> 3) & 1) == 1
                reset_fault_cmd = ((R095_Value >> 4) & 1) == 1
                if reset_fault_cmd and self.faultDetected:
                    self.faultDetected = False
                    self.sm.fire("faultCleared")

            R192 = datastore.getValues(3, self.register_base + 192, count=1)
            if isinstance(R192, list):
                current_R192 = R192[0]
                
                # Check for heartbeat (Bit 7 / SSL708_ClockPulse_CMD)
                xor_diff = current_R192 ^ self.previousR192
                heartbeat_changed = (xor_diff & 128) != 0
                
                if heartbeat_changed:
                    self.last_heartbeat_time = time.time()
                    if self.heartbeat_failed:
                        self.log("Heartbeat restored (R192 Bit 7)")
                        self.heartbeat_failed = False
                
                if current_R192 != self.previousR192:
                    is_heartbeat_only = xor_diff == 128
                    # Log other register changes, but skip the heartbeat toggle noise
                    if not is_heartbeat_only:
                        logger.info(f"[{self.id}] R192 changed: {self.previousR192} -> {current_R192}")
                    
                    self.parse_R192(current_R192)
                    self.previousR192 = current_R192
            
            # Supervision check
            if not self.heartbeat_failed:
                if (time.time() - self.last_heartbeat_time) > self.HEARTBEAT_TIMEOUT:
                    self.log(f"Heartbeat failure: R192 Bit 7 stopped for > {self.HEARTBEAT_TIMEOUT}s")
                    self.heartbeat_failed = True

            # Update state machine and flags first
            self.validate_ssl_flags()
            self.update_state()
            
            # Now calculate simulation dynamics based on current state
            self.update_simulation_dynamics()

            datastore.setValues(3, self.register_base + 129, [int(self.SimulatedActivePower)])
            datastore.setValues(3, self.register_base + 130, [int(self.SimulatedReactivePower)])
            datastore.setValues(3, self.register_base + 76, [int(self.SimulatedFrequency * 100)])
            datastore.setValues(3, self.register_base + 77, [int(self.SimulatedCurrent)])
            datastore.setValues(3, self.register_base + 78, [int(self.SimulatedVoltage)])

            R014 = 0
            if self.SSL['SSL425_ServiceSWOff']: R014 |= (1 << 0)
            if self.SSL['SSL426_ServiceSWManual']: R014 |= (1 << 1)
            if self.SSL['SSL427_ServiceSWAuto']: R014 |= (1 << 2)
            if self.SSL['SSL429_GenCBClosed']: R014 |= (1 << 4)
            if self.SSL['SSL430_GenCBOpen']: R014 |= (1 << 5)
            if self.SSL['SSL431_OperOn']: R014 |= (1 << 6)
            if self.SSL['SSL432_OperOff']: R014 |= (1 << 7)
            if self.SSL['SSL449_OperEngineisRunning']: R014 |= (1 << 8)
            if self.SSL['SSL441_SyncGenActivated']: R014 |= (1 << 9)
            if self.SSL['SSL435_MainsCBClosed']: R014 |= (1 << 10)
            if self.SSL['SSL452_GeneralTrip']: R014 |= (1 << 11)
            if self.SSL['SSL437_TurboChUnitGeneralTrip']: R014 |= (1 << 12)
            if self.SSL['SSL438_TurboChUnitGeneralWarn']: R014 |= (1 << 13)
            if self.SSL['SSL439_IgnSysGeneralTrip']: R014 |= (1 << 14)
            if self.SSL['SSL440_IgnSysGeneralWarn']: R014 |= (1 << 15)
            datastore.setValues(3, self.register_base + 14, [R014])

            R015 = 0
            if self.SSL['SSL441_SyncGenActivated']: R015 |= (1 << 0)
            if self.SSL['SSL443_EngineInStartingPhase']: R015 |= (1 << 2)
            if self.SSL['SSL444_ReadyforAutoDem']: R015 |= (1 << 3)
            if self.SSL['SSL445_DemandforAux']: R015 |= (1 << 4)
            if self.SSL['SSL448_ModuleisDemanded']: R015 |= (1 << 7)
            if self.SSL['SSL449_OperEngineisRunning']: R015 |= (1 << 8)
            if self.SSL['SSL452_GeneralTrip']: R015 |= (1 << 11)
            if self.SSL['SSL453_GeneralWarn']: R015 |= (1 << 12)
            datastore.setValues(3, self.register_base + 15, [R015])

            R023 = 0
            if self.SSL['SSL563_ReadyforFastStart']: R023 |= (1 << 12)
            if self.SSL['SSL564_ModuleLockedOut']: R023 |= (1 << 15)
            datastore.setValues(3, self.register_base + 23, [R023])

            R029 = 0
            if self.SSL['SSL3612_EmergStopPBEngRoom']: R029 |= (1 << 3)
            if self.SSL['SSL3613_EmergStopPBEngVentRoom']: R029 |= (1 << 4)
            if self.SSL['SSL3614_EmergStopPBLVMVCtrlRoom']: R029 |= (1 << 5)
            if self.SSL['SSL3615_EmergStopPBExtCustom']: R029 |= (1 << 6)
            if self.SSL['SSL3616_AuxSupplySource1']: R029 |= (1 << 7)
            if self.SSL['SSL3617_AuxSupplySource2']: R029 |= (1 << 8)
            if self.SSL['SSL3624_TrAppPowExceeded']: R029 |= (1 << 15)
            datastore.setValues(3, self.register_base + 29, [R029])

            R030 = 0
            if self.SSL['SSL3625_EngSmoothLoadRejectStart']: R030 |= (1 << 0)
            if self.SSL['SSL3626_LoadRejWaitforReleaseSync']: R030 |= (1 << 1)
            if self.SSL['SSL3627_GenAntiCondensHeatInOper']: R030 |= (1 << 2)
            if self.SSL['SSL3630_ReleaseLoadAfterGenExcit']: R030 |= (1 << 5)
            datastore.setValues(3, self.register_base + 30, [R030])

            R031 = 0
            if self.SSL['SSL592_EngineAtStandStill']: R031 |= (1 << 1)
            if self.SSL['SSL593_ScaveningInOper']: R031 |= (1 << 2)
            datastore.setValues(3, self.register_base + 31, [R031])

            R109 = 0
            if self.SSL['SSL545_UtilityOperModuleBlocked']: R109 |= (1 << 0)
            if self.SSL['SSL546_GenBreakerOpenFail']: R109 |= (1 << 1)
            if self.SSL['SSL547_GenDeexcited']: R109 |= (1 << 2)
            if self.SSL['SSL548_PowerReductionActivated']: R109 |= (1 << 3)
            if self.SSL['SSL549_LoadRejectedGCBOpen']: R109 |= (1 << 4)
            if self.SSL['SSL550_GenSyncLoadReleas']: R109 |= (1 << 5)
            datastore.setValues(3, self.register_base + 109, [R109])

            if self.sm.state == 'running' and self.SSL['SSL703_MainsCBClosed_CMD'] and self.SSL['SSL430_GenCBOpen']:
                voltage_ready = abs(self.SimulatedVoltage - self.ExcitedVoltage) < VOLTAGE_EPSILON
                frequency_ready = abs(self.SimulatedFrequency - self.NominalFrequency) < FREQUENCY_EPSILON
                if voltage_ready and frequency_ready:
                    self.SSL['SSL429_GenCBClosed'] = True
                    self.SSL['SSL430_GenCBOpen'] = False
                    self.log("CB CLOSED via SSL703_MainsCBClosed_CMD")

            if not self.ssl710PreviousValue and self.SSL['SSL710_OthGCBClosedandExcitOn_CMD']:
                self.deadBusWindowTimer = 3000
                self.log("SSL710 rising edge - 3s dead bus window opened")
            self.ssl710PreviousValue = self.SSL['SSL710_OthGCBClosedandExcitOn_CMD']

            if self.deadBusWindowTimer > 0:
                # Fix: Clamp timer to zero to prevent negative values
                self.deadBusWindowTimer = max(0, self.deadBusWindowTimer - self.dt)
                if (self.sm.state == 'running' and self.SSL['SSL430_GenCBOpen'] and
                    self.SSL['SSL547_GenDeexcited'] and self.SSL['SSL704_EnGenBreakerActToDeadBus_CMD']):
                    self.SSL['SSL429_GenCBClosed'] = True
                    self.SSL['SSL430_GenCBOpen'] = False
                    self.log("CB CLOSED during 3s dead bus window (de-excited)")


class SwitchgearController:
    def __init__(self, gps_id: str, register_base: int, ip_address: str = ""):
        self.id = gps_id
        self.register_base = register_base
        self.ip_address = ip_address

    def tick(self, generators: List[GeneratorController], datastore: ModbusDeviceContext):
        
        P74 = datastore.getValues(3, self.register_base + 74, count=1)
        total_demand = P74[0] if isinstance(P74, list) else 0
        online = []
        for gen in generators:
            assign = False
            if gen.id in ["G1", "G2", "G3", "G4", "G5"]:
                if gen.FCB1 and self.id == "GPS1": assign = True
                if gen.FCB2 and self.id == "GPS2": assign = True
            elif gen.id in ["G6", "G7", "G8", "G9", "G10"]:
                if gen.FCB1 and self.id == "GPS2": assign = True
                if gen.FCB2 and self.id == "GPS1": assign = True
            elif gen.id in ["G11", "G12", "G13", "G14", "G15"]:
                if gen.FCB1 and self.id == "GPS3": assign = True
                if gen.FCB2 and self.id == "GPS4": assign = True
            elif gen.id in ["G16", "G17", "G18", "G19", "G20"]:
                if gen.FCB1 and self.id == "GPS4": assign = True
                if gen.FCB2 and self.id == "GPS3": assign = True
            elif gen.id == "G21":
                if gen.FCB1 and self.id == "GPS1": assign = True
                if gen.FCB2 and self.id == "GPS3": assign = True
            elif gen.id == "G22":
                if gen.FCB1 and self.id == "GPS2": assign = True
                if gen.FCB2 and self.id == "GPS4": assign = True
            if assign and gen.state == GeneratorState.RUNNING:
                online.append(gen)
        
        count = len(online)
        if count > 0:
            # Fix: True proportional distribution based on generator capacity
            total_capacity = sum(gen.NominalPower for gen in online)
            if total_demand > total_capacity:
                logger.warning(f"[{self.id}] Overload: Demand {total_demand} kW exceeds capacity {total_capacity} kW")
                # Distribute proportionally to each generator's capacity
                for gen in online:
                    proportional_share = total_demand * (gen.NominalPower / total_capacity)
                    gen.rSetpointPower = min(proportional_share, gen.NominalPower)
            else:
                # Normal operation: distribute proportionally to capacity
                for gen in online:
                    proportional_share = total_demand * (gen.NominalPower / total_capacity)
                    gen.rSetpointPower = proportional_share
        else:
            per_load = 0
        
        datastore.setValues(3, self.register_base + 901, [count])


class IndividualModbusServer:
    """Individual Modbus TCP server for a single generator or switchgear"""
    def __init__(self, name: str, ip_address: str, port: int, controller):
        self.name = name
        self.ip_address = ip_address
        self.port = port
        self.controller = controller
        self.datastore: Optional[ModbusDeviceContext] = None
        self.context: Optional[ModbusServerContext] = None
        self.running = False
        # Fix: Add lock for thread-safe datastore access
        self.datastore_lock = threading.Lock()
        
    def _initialize_registers(self) -> ModbusDeviceContext:
        num_registers = 1000
        hr = ModbusSequentialDataBlock(0, [0] * num_registers)
        store = ModbusDeviceContext(
            di=ModbusSequentialDataBlock(0, [0] * num_registers),
            co=ModbusSequentialDataBlock(0, [0] * num_registers),
            hr=hr,
            ir=ModbusSequentialDataBlock(0, [0] * num_registers)
        )
        # Initialize command registers to 0
        store.setValues(3, 95, [0])   # R095 - Fault simulation flags
        store.setValues(3, 192, [0])  # R192 - Command word
        return store
    
    async def _run_server_async(self):
        if self.context is None:
            raise RuntimeError("Server context not initialized")
        logger.info(f"Starting Modbus server for {self.name} on {self.ip_address}:{self.port}")
        await StartAsyncTcpServer(context=self.context, address=(self.ip_address, self.port))
    
    def _run_server_thread(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_server_async())
        except Exception as e:
            logger.error(f"Server error for {self.name}: {e}")
    
    def _simulation_loop(self):
        while self.running:
            if self.datastore is None:
                time.sleep(0.1)
                continue
            try:
                # Fix: Use lock for thread-safe datastore access
                with self.datastore_lock:
                    if hasattr(self.controller, 'tick'):
                        if isinstance(self.controller, GeneratorController):
                            self.controller.tick(self.datastore)
                        elif isinstance(self.controller, SwitchgearController):
                            # Switchgear needs generator list - will be set by parent
                            pass
            except Exception as e:
                logger.error(f"Simulation error for {self.name}: {e}")
            time.sleep(0.1)
    
    def start(self):
        self.datastore = self._initialize_registers()
        self.context = ModbusServerContext(devices={1: self.datastore}, single=False)
        self.running = True
        threading.Thread(target=self._run_server_thread, daemon=True, name=f"Server-{self.name}").start()
        threading.Thread(target=self._simulation_loop, daemon=True, name=f"Sim-{self.name}").start()
        logger.info(f"✓ {self.name} started on {self.ip_address}:{self.port}")
    
    def stop(self):
        self.running = False


class ModbusTCPSlaveGenRun:
    def __init__(self, port: int = 502, num_generators: int = 22, scan_interval: float = 0.1):
        self.port = port
        self.scan_interval = scan_interval
        self.running = False
        self.generators: List[GeneratorController] = []
        self.switchgears: List[SwitchgearController] = []
        self.servers: List[IndividualModbusServer] = []
        
        # Create generators with register base 0 (each has own server)
        for i in range(1, num_generators + 1):
            gen_id = f"G{i}"
            ip_address = GEN_IP_MAP.get(gen_id, "127.0.0.1")
            gen = GeneratorController(gen_id, register_base=0, ip_address=ip_address)
            self.generators.append(gen)
            
            # Create individual server for this generator
            server = IndividualModbusServer(gen_id, ip_address, self.port, gen)
            self.servers.append(server)
        
        # Create switchgears with register base 0 (each has own server)
        for i in range(1, 5):
            gps_id = f"GPS{i}"
            ip_address = SWG_IP_MAP.get(gps_id, "127.0.0.1")
            swg = SwitchgearController(gps_id, register_base=0, ip_address=ip_address)
            self.switchgears.append(swg)
            
            # Create individual server for this switchgear
            server = IndividualModbusServer(gps_id, ip_address, self.port, swg)
            self.servers.append(server)
        
        logger.info(f"Initialized {len(self.generators)} generators and {len(self.switchgears)} switchgears")

    def _global_simulation_loop(self):
        """Coordinate switchgear logic across all generators"""
        while self.running:
            try:
                for swg_server in [s for s in self.servers if isinstance(s.controller, SwitchgearController)]:
                    if swg_server.datastore:
                        # Fix: Use lock for thread-safe datastore access
                        with swg_server.datastore_lock:
                            swg_server.controller.tick(self.generators, swg_server.datastore)
            except Exception as e:
                logger.error(f"Global simulation error: {e}")
            time.sleep(self.scan_interval)

    def start(self):
        self.running = True
        logger.info("Starting all Modbus TCP servers...")
        
        # Start all individual servers
        for server in self.servers:
            server.start()
            time.sleep(0.1)  # Small delay between server starts
        
        # Start global coordination loop
        threading.Thread(target=self._global_simulation_loop, daemon=True, name="GlobalSim").start()
        
        logger.info(f"✓ All {len(self.servers)} servers started successfully")

    def stop(self):
        self.running = False
        logger.info("Stopping all servers...")
        for server in self.servers:
            server.stop()


def main():
    logging.basicConfig(level=logging.INFO)
    slave = ModbusTCPSlaveGenRun()
    try:
        slave.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        slave.stop()


if __name__ == "__main__":
    main()
