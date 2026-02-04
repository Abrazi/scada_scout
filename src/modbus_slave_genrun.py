"""
Modbus TCP Slave with GenRun Generator Simulation Logic
Converted from GenRun_Edited.js to Python for SCADA Scout application
"""

import logging
import threading
import time
import math
from typing import Optional, List, Dict, Callable
from enum import IntEnum
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusDeviceContext, ModbusServerContext
import asyncio

logger = logging.getLogger(__name__)

VOLTAGE_EPSILON = 10
FREQUENCY_EPSILON = 0.1
POWER_EPSILON = 10

class GeneratorState(IntEnum):
    STANDSTILL = 0
    STARTING = 1
    RUNNING = 2
    SHUTDOWN = 3
    FAULT = 4
    FAST_TRANSFER = 5

class StateMachine:
    def __init__(self, initial_state: str):
        self.state = initial_state
        self.transitions: Dict[str, Dict[str, str]] = {}
        self.ignored_triggers: Dict[str, List[str]] = {}
        
    def add_transition(self, from_state: str, trigger: str, to_state: str):
        if from_state not in self.transitions:
            self.transitions[from_state] = {}
        self.transitions[from_state][trigger] = to_state
        
    def add_ignore(self, state: str, trigger: str):
        if state not in self.ignored_triggers:
            self.ignored_triggers[state] = []
        self.ignored_triggers[state].append(trigger)
        
    def fire(self, trigger: str) -> bool:
        if self.state in self.ignored_triggers and trigger in self.ignored_triggers[self.state]:
            return False
        if self.state in self.transitions and trigger in self.transitions[self.state]:
            self.state = self.transitions[self.state][trigger]
            return True
        return False

class GeneratorController:
    def __init__(self, gen_id: str, register_base: int):
        self.id = gen_id
        self.register_base = register_base
        self.last_processed_state = None
        
        self.DeExcitedVoltage = 3500.0
        self.ExcitedVoltage = 10500.0
        self.rVoltage = 0.0
        self.NominalFrequency = 50.0
        self.NominalPower = 3500.0
        
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
        
    def log(self, level: int, message: str):
        if level <= 2:
            logger.info(f"[{self.id}] [{self.sm.state}] {message}")
            
    def ramp(self, value: float, target: float, rate: float, fail_flag: bool, param_type: str) -> float:
        if fail_flag:
            return value
        delta = rate * self.dt / 1000.0
        if value < target:
            new_value = min(target, value + delta)
        elif value > target:
            new_value = max(target, value - delta)
        else:
            new_value = value
        if param_type == 'power':
            return min(max(new_value, 0), self.NominalPower)
        elif param_type == 'voltage':
            return min(max(new_value, 0), self.ExcitedVoltage)
        elif param_type == 'frequency':
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
            ('SSL708_ClockPulse_CMD', 7),
            ('SSL709_GenExcitationOff_CMD', 8),
            ('SSL710_OthGCBClosedandExcitOn_CMD', 9)
        ]
        for flag_name, bit in flags:
            self.SSL[flag_name] = ((value >> bit) & 1) == 1
            
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
        self.log(1, "ENTERING STATE: Standstill")
        self.reset_outputs()
        
    def on_enter_starting(self):
        self.log(1, "ENTERING STATE: Starting")
        self.startTimer = 0
        self.SSL['SSL431_OperOn'] = True
        self.SSL['SSL432_OperOff'] = False
        self.SSL['SSL448_ModuleisDemanded'] = True
        self.SSL['SSL592_EngineAtStandStill'] = False
        
    def on_enter_running(self):
        self.log(1, "ENTERING STATE: Running")
        self.SSL['SSL550_GenSyncLoadReleas'] = True
        self.SSL['SSL547_GenDeexcited'] = True
        self.SSL['SSL448_ModuleisDemanded'] = True
        self.SSL['SSL444_ReadyforAutoDem'] = False
        
    def on_enter_shutdown(self):
        self.log(1, "ENTERING STATE: Shutdown")
        self.stopTimer = 0
        self.SSL['SSL448_ModuleisDemanded'] = False
        
    def on_enter_fault(self):
        self.log(1, "ENTERING STATE: Fault")
        self.reset_outputs()
        
    def on_enter_fast_transfer(self):
        self.log(1, "ENTERING STATE: FastTransfer")
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
            self.log(2, f"STATE TRANSITION: {self.last_processed_state} -> {current_state}")
            func_name = f"on_enter_{current_state}"
            if hasattr(self, func_name):
                getattr(self, func_name)()
            self.last_processed_state = current_state
            self.state = GeneratorState[current_state.upper()]
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
                        self.log(2, "CB CLOSED to dead busbar (SSL704)")
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
                            self.log(2, "CB CLOSED via auto-sync to live busbar")
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
                self.log(2, f"CB OPENED - power below 10% ({self.SimulatedActivePower:.1f} kW)")
            if is_power_zero and self.stopTimer >= self.StopDelay:
                self.log(2, "Shutdown complete - transitioning to standstill")
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
        if self.SSL['SSL709_GenExcitationOff_CMD']:
            self.SSL['SSL547_GenDeexcited'] = True
        else:
            self.SSL['SSL547_GenDeexcited'] = False
        if self.SSL['SSL705_LoadRejectGenCBOpen_CMD']:
            self.SSL['SSL549_LoadRejectedGCBOpen'] = True
        else:
            self.SSL['SSL549_LoadRejectedGCBOpen'] = False
            
    def update_simulation_dynamics(self):
        if self.sm.state == 'standstill' or self.sm.state == 'fault':
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
        self.SimulatedReactivePower = self.ramp(self.SimulatedReactivePower, target_reactive_power, current_reactive_power_ramp_rate, fail_reactive_ramp_flag, 'power')
        if (self.SSL['SSL430_GenCBOpen'] and self.sm.state != 'starting') or self.sm.state in ['standstill', 'fault']:
            self.SimulatedReactivePower = 0.0
        P_kW = self.SimulatedActivePower
        Q_kVAr = self.SimulatedReactivePower
        S_kVA = math.sqrt(P_kW * P_kW + Q_kVAr * Q_kVAr)
        if self.SimulatedVoltage > VOLTAGE_EPSILON:
            self.SimulatedCurrent = (S_kVA * 1000) / (self.SimulatedVoltage * 1.732)
        else:
            self.SimulatedCurrent = 0.0
            
    def tick(self, datastore: ModbusDeviceContext):
        with self.lock:
            try:
                self.update_simulation_dynamics()
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
                    self.parse_R192(R192[0])
                self.validate_ssl_flags()
                self.update_state()
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
                        self.log(2, "CB CLOSED via SSL703_MainsCBClosed_CMD")
                if not self.ssl710PreviousValue and self.SSL['SSL710_OthGCBClosedandExcitOn_CMD']:
                    self.deadBusWindowTimer = 3000
                    self.log(2, "SSL710 rising edge - 3s dead bus window opened")
                self.ssl710PreviousValue = self.SSL['SSL710_OthGCBClosedandExcitOn_CMD']
                if self.deadBusWindowTimer > 0:
                    self.deadBusWindowTimer -= self.dt
                    if (self.sm.state == 'running' and self.SSL['SSL430_GenCBOpen'] and 
                        self.SSL['SSL547_GenDeexcited'] and self.SSL['SSL704_EnGenBreakerActToDeadBus_CMD']):
                        self.SSL['SSL429_GenCBClosed'] = True
                        self.SSL['SSL430_GenCBOpen'] = False
                        self.log(2, "CB CLOSED during 3s dead bus window (de-excited)")
            except Exception as e:
                logger.error(f"Error in generator {self.id} tick: {e}", exc_info=True)
                self.faultDetected = True
                if self.sm.state != "fault":
                    self.sm.fire("faultDetected")

class SwitchgearController:
    def __init__(self, gps_id: str, register_base: int):
        self.id = gps_id
        self.register_base = register_base
        
    def tick(self, generators: List[GeneratorController], datastore: ModbusDeviceContext):
        P74 = datastore.getValues(3, self.register_base + 74, count=1)
        total_demand = P74[0] if isinstance(P74, list) else 0
        online_generators = []
        for gen in generators:
            assign_to_this = False
            if gen.id in ["G1", "G2", "G3", "G4", "G5"]:
                if gen.FCB1 and self.id == "GPS1": assign_to_this = True
                if gen.FCB2 and self.id == "GPS2": assign_to_this = True
            elif gen.id in ["G6", "G7", "G8", "G9", "G10"]:
                if gen.FCB1 and self.id == "GPS2": assign_to_this = True
                if gen.FCB2 and self.id == "GPS1": assign_to_this = True
            elif gen.id in ["G11", "G12", "G13", "G14", "G15"]:
                if gen.FCB1 and self.id == "GPS3": assign_to_this = True
                if gen.FCB2 and self.id == "GPS4": assign_to_this = True
            elif gen.id in ["G16", "G17", "G18", "G19", "G20"]:
                if gen.FCB1 and self.id == "GPS4": assign_to_this = True
                if gen.FCB2 and self.id == "GPS3": assign_to_this = True
            elif gen.id == "G21":
                if gen.FCB1 and self.id == "GPS1": assign_to_this = True
                if gen.FCB2 and self.id == "GPS3": assign_to_this = True
            elif gen.id == "G22":
                if gen.FCB1 and self.id == "GPS2": assign_to_this = True
                if gen.FCB2 and self.id == "GPS4": assign_to_this = True
            if assign_to_this and gen.state == GeneratorState.RUNNING:
                online_generators.append(gen)
        count = len(online_generators)
        per_gen_load = (total_demand / count) if count > 0 else 0
        for gen in online_generators:
            gen.rSetpointPower = per_gen_load
        datastore.setValues(3, self.register_base + 901, [count])

class ModbusTCPSlaveGenRun:
    def __init__(self, address: str = "127.0.0.1", port: int = 5020, num_generators: int = 22, scan_interval: float = 0.1):
        self.address = address
        self.port = port
        self.scan_interval = scan_interval
        self.datastore: Optional[ModbusDeviceContext] = None
        self.context: Optional[ModbusServerContext] = None
        self.running = False
        self.generators: List[GeneratorController] = []
        self.switchgears: List[SwitchgearController] = []
        for i in range(1, num_generators + 1):
            gen_id = f"G{i}"
            register_base = (i - 1) * 200
            self.generators.append(GeneratorController(gen_id, register_base))
        for i in range(1, 5):
            gps_id = f"GPS{i}"
            register_base = 5000 + (i - 1) * 200
            self.switchgears.append(SwitchgearController(gps_id, register_base))
        logger.info(f"ModbusTCPSlaveGenRun initialized: {address}:{port}, {num_generators} generators, {len(self.switchgears)} switchgears")
        
    def _initialize_registers(self) -> ModbusDeviceContext:
        num_registers = 6000
        hr = ModbusSequentialDataBlock(0, [0] * num_registers)
        store = ModbusDeviceContext(
            di=ModbusSequentialDataBlock(0, [0] * num_registers),
            co=ModbusSequentialDataBlock(0, [0] * num_registers),
            hr=hr,
            ir=ModbusSequentialDataBlock(0, [0] * num_registers)
        )
        logger.info(f"Register datastore initialized with {num_registers} registers")
        return store
        
    async def _run_server_async(self):
        try:
            if self.context is None:
                raise RuntimeError("Server context not initialized")
            logger.info(f"Starting Modbus TCP server on {self.address}:{self.port}")
            await StartAsyncTcpServer(
                context=self.context,
                address=(self.address, self.port)
            )
        except Exception as e:
            logger.error(f"Modbus server error: {e}", exc_info=True)
            self.running = False
            
    def _run_server_thread(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_server_async())
        except Exception as e:
            logger.error(f"Server thread error: {e}", exc_info=True)
        finally:
            self.running = False
            
    def _simulation_loop(self):
        logger.info("Simulation loop started")
        while self.running:
            try:
                if self.datastore is None:
                    time.sleep(self.scan_interval)
                    continue
                for swg in self.switchgears:
                    swg.tick(self.generators, self.datastore)
                for gen in self.generators:
                    gen.tick(self.datastore)
                time.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}", exc_info=True)
                time.sleep(0.1)
        logger.info("Simulation loop stopped")
        
    def start(self):
        if self.running:
            logger.warning("Modbus slave already running")
            return
        try:
            self.datastore = self._initialize_registers()
            self.context = ModbusServerContext(devices={1: self.datastore}, single=False)
            self.running = True
            server_thread = threading.Thread(target=self._run_server_thread, daemon=True)
            server_thread.start()
            sim_thread = threading.Thread(target=self._simulation_loop, daemon=True)
            sim_thread.start()
            logger.info("ModbusTCPSlaveGenRun started successfully")
        except Exception as e:
            logger.error(f"Failed to start: {e}", exc_info=True)
            self.stop()
            raise
            
    def stop(self):
        if not self.running:
            return
        logger.info("Stopping ModbusTCPSlaveGenRun...")
        self.running = False
        logger.info("ModbusTCPSlaveGenRun stopped")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    slave = ModbusTCPSlaveGenRun(
        address="127.0.0.1",
        port=5020,
        num_generators=22,
        scan_interval=0.1
    )
    try:
        print("=" * 60)
        print("Modbus TCP Slave - GenRun Generator Simulation")
        print("=" * 60)
        print(f"Server Address: {slave.address}:{slave.port}")
        print(f"Generators: 22 (G1-G22)")
        print(f"Switchgears: 4 (GPS1-GPS4)")
        print("\nRegister Layout per Generator (200 registers each):")
        print("  R014: Service switch & CB status")
        print("  R015: SSL operational flags")
        print("  R023: Readiness & lockout")
        print("  R029: Emergency stops & aux supply")
        print("  R030: Load rejection & excitation")
        print("  R031: Engine idle status")
        print("  R076: Frequency (0.1 Hz)")
        print("  R077: Current (A)")
        print("  R078: Voltage (V)")
        print("  R095: Fault simulation control")
        print("  R109: Blocking & alarm flags")
        print("  R129: Active Power (kW)")
        print("  R130: Reactive Power (kVAr)")
        print("  R192: Command word (SSL701-SSL710)")
        print("\nSwitchgear Registers (base 5000+):")
        print("  P74: Total demand (kW)")
        print("  R901: Running generator count")
        print("\nPress Ctrl+C to stop...")
        print("=" * 60)
        slave.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        slave.stop()
        print("Server stopped.")

if __name__ == "__main__":
    main()
