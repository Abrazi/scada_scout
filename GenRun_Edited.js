//big edit Edited by: Majid Date: 22 Dec. 2025 time: 15:00

// OVERVIEW:
// This script simulates the behavior of multiple generators (GeneratorController instances)
// and their interaction with switchgear systems (SwitchgearController instances).
// Key functionalities include:
//   - Generator state machine control (standstill, starting, running, shutdown, fault, fast transfer).
//   - Simulation of electrical parameters (voltage, frequency, active/reactive power, current)
//     with ramping logic.
//   - Modbus communication for reading commands/setpoints and writing simulated data/status.
//   - Load sharing logic distributed by SwitchgearControllers to assigned online generators.
//   - Management of numerous status and command flags (SSL - Signal Status Logic).
//   - Fault simulation and handling capabilities.
// The JavaScript is intended for use within Triangle Microworks DTM Insight Java environment that provides the necessary
// API functions for Modbus access, state machine primitives, and basic scripting utilities.

// SCRIPT EXECUTION ENVIRONMENT DEPENDENCIES:
// This script relies on several functions and objects being provided by its host execution Triangle Microworks DTM Insight Java environment.
// These include, but are not limited to:
//


// verbosity for debug logging:
// 0 = off
// 1 = Important/General Logs
// 2 = State Changes & Faults
// 3 = Modbus Register Writes
// 4 = Key Variable Changes
// 5 = R109 Register
var _verbose = 2; // Default level

// Tolerance constants for floating-point comparisons
var VOLTAGE_EPSILON = 10;    // Voltage tolerance in V
var FREQUENCY_EPSILON = 0.1; // Frequency tolerance in Hz
var POWER_EPSILON = 10;      // Power tolerance in kW

// Cycle timing variables
var lastCycleTime = 0;
var maxCycleDuration = 0;
var lastLoopTime = Date.now();

print('Script starting...\n');

// State constants and name array for generator state machine
var state = {
    STANDSTILL: 0,
    STARTING: 1,
    RUNNING: 2,
    SHUTDOWN: 3,
    FAULT: 4,
    FAST_TRANSFER: 5
};

var stateName = ["standstill", "starting", "running", "shutdown", "fault", "fastTransfer"];

// Control constants and name array for generator control Mode
var control = {
    MANUAL: -1,
    AUTO: 1,
};

var ControlName = ["manual", "auto"];

// State machine triggers for generator control
var triggers = {
    DEMAND: "demand",              // Demand signal received
    DEEXCITE: "deexcite",         // De-excitation command
    EXCITE: "excite",             // Excitation command
    START_COMPLETE: "startComplete", // Starting sequence completed
    FAULT_DETECTED: "faultDetected", // Fault condition detected
    FAULT_CLEARED: "faultCleared",   // Fault condition cleared
    SHUTDOWN_REQUEST: "shutdown",     // Shutdown requested
    TRANSFER_REQUEST: "transfer",     // Fast transfer requested
    VOLTAGE_READY: "voltageReady",   // Voltage reached target
    FREQUENCY_READY: "freqReady",    // Frequency reached target
    POWER_ZERO: "powerZero"          // Power ramped to zero
};

  
  
  // // Helper to create global callback functions
// function createGlobalCallback(name, func) {
    // // Define the function in global scope
    // eval("this." + name + " = " + func.toString().replace(/^function\s*\(/, "function " + name + "("));
// }
  
// Global array to hold all generator instances (will be populated later)
//var generators = [];

// // Helper function to find a generator instance by its ID
// function findGeneratorById(id) {
    // for (var i = 0; i < generators.length; i++) {
        // if (generators[i] && generators[i].id === id) {
            // return generators[i];
        // }
    // }
    // return null;
// }  
  
  
// GeneratorController constructor:
// Initializes simulation parameters for a specific generator instance.
// 'id' represents the generator name like "G1", "G2", etc. It is used to construct
// tag paths for Modbus communication, so each instance manages its own data.
function GeneratorController(id) {
    if (!id || typeof id !== 'string') {
        throw new Error('Invalid generator ID');
    }
    this.id = id;
    this.path = "/GEN/" + id + "/sMB/sMB&&&sMB.sMB.T4.";
    
    // track state transitions
    this.lastProcessedState = null;
    
     //SetOnEnterStateFun 
     
    //
    // 1) DESIGN & RAMP CONFIGURATION
    //
    this.DeExcitedVoltage = 3500.0; // V
    this.ExcitedVoltage = 10500.0; // V
    this.rVoltage = 0.0; // generator requested/traget voltage V

    this.NominalFrequency = 50.0;   // Hz
    this.NominalPower = 3500.0; // kW

    // how fast we ramp V/F/P per second
    this.RampRateVoltage = 10000.0;  // V/sec
    this.RampRateFrequency = 200;    // Hz/sec
    this.RampRatePowerUp = 10000.0;  // kW/sec
    this.RampRatePowerDown = 10000.0;  // kW/sec

    // droop for active power sharing (not used heavily here)
    this.DroopCoefficient = 1.0;

    //
    // 2) TIMERS & TIMESTEP
    //
    this.dt = 100;    // ms per cycle
    this.StartDelay = 100;   // ms to stay in STARTING before RUNNING
    this.StopDelay = 100;   // ms to fully stop
    this.startTimer = 0;
    this.stopTimer = 1;
    this.GenCBTimer = 0;
    this.blackoutTimer = 0;
    this.deadBusWindowTimer = 0;  // Timer for 7-second dead bus window 
    this.ssl710PreviousValue = false;  // Track SSL710 for edge detection

    //
    // 3) STATE MACHINE & FLAGS
    //
    this.state = state.STANDSTILL;    // 
    this.GeneratorState = -1;   // last published
    this.faultDetected = false;

    // simulation failure injections
    this.SimulateFailToStart = false;  // force a startup fault
    this.FailRampUp = false;  // disable ramp up
    this.FailRampDown = false;  // disable ramp down
    this.FailStartTime = false;  // pretend StartDelay never reached


    // de-excitation logic (for reconnect)
    this.isDeexcited = false;

    //
    // 4) OUTPUTS (simulated)
    //
    this.SimulatedVoltage = 0.0;   // V
    this.SimulatedFrequency = 0.0;   // Hz
    this.SimulatedCurrent = 0.0;   // A
    this.SimulatedActivePower = 0.0;   // kW
    this.SimulatedReactivePower = 0.0;   // kVAr

    // set-points commanded by central controller / SCADA
    this.rSetpointPower = 0.0;   // requewted kW
    this.rSetpointReactivePower = 0.0;   // requested kVAr

    // Initialize previous values for change tracking
    this.previousSetpointPower = this.rSetpointPower;
    this.previousSetpointReactivePower = this.rSetpointReactivePower; // Initialize for tracking

    // 5) FCB / GPS LOGIC (future IEC-61850 inputs)
    // FCB tags: these will be read from IEC 61850
    // FCB1 and FCB2 represent breaker signals / GPS connectivity status which couldbe a combination of other CB status or SCADA signal -> to be checked 


    // FCB1 and FCB2 determine which switchgear this generator is connected to
    // For swing generators (G21, G22), FCB1 and FCB2 select between two GPS groups
    this.FCB1 = true;   // Target switchgear ID (e.g., "GPS1")
    this.FCB2 = false;


    // SSL: Signal Status Logic – container for all control/status flags
    // These flags represent various states, conditions, and commands for the generator.
    // Defaults are set to a typical idle/ready state.
    this.SSL = {
        // Service Switch Status (Usually, only one of these is true)
        SSL425_ServiceSWOff: false,           // Service switch is in OFF position
        SSL426_ServiceSWManual: false,        // Service switch is in MANUAL position
        SSL427_ServiceSWAuto: true,           // Service switch is in AUTO position (Default)

        // Generator Circuit Breaker (CB) Status (Mutually exclusive)
        SSL429_GenCBClosed: false,            // Generator CB is closed
        SSL430_GenCBOpen: true,               // Generator CB is open (Default)

        // Operational Status (Mutually exclusive)
        SSL431_OperOn: false,                 // Generator is in operation
        SSL432_OperOff: true,                // Generator is not in operation (Default)
        SSL435_MainsCBClosed: false,          // Mains (Utility) CB is closed

        // Trip and Warning Flags (Specific unit trips/warnings)
        SSL437_TurboChUnitGeneralTrip: false, // Turbocharger unit general trip
        SSL438_TurboChUnitGeneralWarn: false, // Turbocharger unit general warning
        SSL439_IgnSysGeneralTrip: false,      // Ignition system general trip
        SSL440_IgnSysGeneralWarn: false,      // Ignition system general warning

        // Generator Functional Status
        SSL441_SyncGenActivated: false,       // Synchronizing generator activated
        SSL443_EngineInStartingPhase: false,  // Engine is currently in its starting phase
        SSL444_ReadyforAutoDem: true,         // Ready for automatic demand (Default)
        SSL445_DemandforAux: false,           // Demand for auxiliary systems
        SSL448_ModuleisDemanded: false,       // Module (generator) is demanded/requested to run
        SSL449_OperEngineisRunning: false,    // Engine is running

        // General System Status
        SSL452_GeneralTrip: false,            // General trip for the entire module
        SSL453_GeneralWarn: false,            // General warning for the entire module

        // Utility Interaction and Advanced Breaker Status
        SSL545_UtilityOperModuleBlocked: false, // Utility operation module blocked
        SSL546_GenBreakerOpenFail: false,     // Generator breaker failed to open
        SSL547_GenDeexcited: false,           // Generator is de-excited
        SSL548_PowerReductionActivated: false, // Power reduction is active
        SSL549_LoadRejectedGCBOpen: false,    // Load rejection, GCB is open
        SSL550_GenSyncLoadReleas: false,      // Generator synchronized, load released for connection

        // Readiness and Lockout Status
        SSL563_ReadyforFastStart: false,      // Module is ready for a fast start sequence
        SSL564_ModuleLockedOut: false,        // Module is locked out (cannot operate)

        // Engine Specific Status
        SSL592_EngineAtStandStill: true,      // Engine is at a standstill (Default)
        SSL593_ScaveningInOper: false,        // Scavenging (pre-start air purge) is in operation

        // Emergency Stop Pushbutton (PB) Flags
        SSL3612_EmergStopPBEngRoom: false,       // Emergency stop PB in Engine Room activated
        SSL3613_EmergStopPBEngVentRoom: false,   // Emergency stop PB in Engine Ventilation Room activated
        SSL3614_EmergStopPBLVMVCtrlRoom: false,  // Emergency stop PB in LV/MV Control Room activated
        SSL3615_EmergStopPBExtCustom: false,     // Emergency stop PB External/Custom activated

        // Auxiliary Supply Status
        SSL3616_AuxSupplySource1: false,      // Auxiliary supply source 1 active
        SSL3617_AuxSupplySource2: false,      // Auxiliary supply source 2 active
        SSL3624_TrAppPowExceeded: false,      // Transformer apparent power exceeded

        // Engine and Load Management Status
        SSL3625_EngSmoothLoadRejectStart: false, // Engine smooth load rejection started
        SSL3626_LoadRejWaitforReleaseSync: false,// Load rejection, waiting for release/synchronization
        SSL3627_GenAntiCondensHeatInOper: false, // Generator anti-condensation heater in operation
        SSL3630_ReleaseLoadAfterGenExcit: false, // Release load after generator excitation

        // Command Flags (Inputs from SCADA/Control System via Modbus R192 or other means)
        SSL701_DemandModule_CMD: false,             // Command: Demand module to start/run
        SSL702_UtilityOperModuleBlocked_CMD: false, // Command: Block module by utility operation
        SSL703_MainsCBClosed_CMD: false,            // Command/Status: Mains CB is closed (can be feedback or command)
        SSL704_EnGenBreakerActToDeadBus_CMD: false, // Command: Enable generator breaker activation to a dead bus
        SSL705_LoadRejectGenCBOpen_CMD: false,      // Command: Initiate load rejection, open GCB
        SSL706_AuxPowSuppSource1_CMD: false,        // Command: Select auxiliary power supply source 1
        SSL707_AuxPowSuppSource2_CMD: false,        // Command: Select auxiliary power supply source 2
        SSL708_ClockPulse_CMD: false,               // Command: Clock pulse (for synchronization or timed operations)
        SSL709_GenExcitationOff_CMD: false,         // Command: Turn generator excitation off
        SSL710_OthGCBClosedandExcitOn_CMD: false    // Status/Condition: Other GCB on bus is closed and its generator is excited
    };

    // To track Modbus values and log only on change for efficiency and clarity
    this.previousModbusValues = {};

    // Initialize state machine
    this.sm = CreateStateMachine("standstill");

    // Configure states
    this.standstillState = ConfigureState(this.sm, "standstill");
    this.startingState = ConfigureState(this.sm, "starting");
    this.runningState = ConfigureState(this.sm, "running");
    this.shutdownState = ConfigureState(this.sm, "shutdown");
    this.faultState = ConfigureState(this.sm, "fault");
    this.fastTransferState = ConfigureState(this.sm, "fastTransfer");

    // Configure transitions
    // From Standstill
    ConfigurePermit(this.standstillState, triggers.DEMAND, "starting");
    ConfigurePermit(this.standstillState, triggers.FAULT_DETECTED, "fault");

    // From Starting - Use ConfigureIgnore for same-state triggers
    ConfigureIgnore(this.startingState, triggers.VOLTAGE_READY);  // Allow voltage ready without state change
    ConfigureIgnore(this.startingState, triggers.FREQUENCY_READY);  // Allow frequency ready without state change
    ConfigurePermit(this.startingState, triggers.START_COMPLETE, "running");
    ConfigurePermit(this.startingState, triggers.SHUTDOWN_REQUEST, "shutdown");
    ConfigurePermit(this.startingState, triggers.FAULT_DETECTED, "fault");

    // From Running
    ConfigurePermit(this.runningState, triggers.SHUTDOWN_REQUEST, "shutdown");
    ConfigurePermit(this.runningState, triggers.TRANSFER_REQUEST, "fastTransfer");
    ConfigurePermit(this.runningState, triggers.FAULT_DETECTED, "fault");

    // From Shutdown
    ConfigurePermit(this.shutdownState, triggers.POWER_ZERO, "standstill");
    ConfigurePermit(this.shutdownState, triggers.FAULT_DETECTED, "fault");

    // From Fault
    ConfigurePermit(this.faultState, triggers.FAULT_CLEARED, "standstill");
    ConfigurePermit(this.faultState, triggers.SHUTDOWN_REQUEST, "shutdown");

    // From Fast Transfer
    ConfigurePermit(this.fastTransferState, triggers.DEMAND, "running");
    ConfigurePermit(this.fastTransferState, triggers.SHUTDOWN_REQUEST, "shutdown");
    ConfigurePermit(this.fastTransferState, triggers.FAULT_DETECTED, "fault");

    // Create state callback functions in the instance scope
      // ALTERNATIVE MINIMAL FIX: Replace lines ~330-360 with this simpler approach
// This creates the wrapper functions BEFORE eval, ensuring they're defined

 // Create state callback functions as instance methods
    this.onEnterStandstill = function () {
        this.log(1, "ENTERING STATE: Standstill");
        this.resetOutputs();
    };

    this.onEnterStarting = function () {
        this.log(1, "ENTERING STATE: Starting");
        this.startTimer = 0;
        this.SSL.SSL431_OperOn = true;
        this.SSL.SSL432_OperOff = false;
        this.SSL.SSL448_ModuleisDemanded = true;
        this.SSL.SSL592_EngineAtStandStill = false;

        //if (this.SSL.SSL709_GenExcitationOff_CMD) {
        //    this.SSL.SSL547_GenDeexcited = true;
        //    this.SSL.SSL550_GenSyncLoadReleas = true;
        //    this.SSL.SSL448_ModuleisDemanded = true;
        //}
    };

    this.onEnterRunning = function () {
        this.log(1, "ENTERING STATE: Running");
        this.SSL.SSL550_GenSyncLoadReleas = true;
        this.SSL.SSL547_GenDeexcited = true;
        this.SSL.SSL448_ModuleisDemanded = true;
        this.SSL.SSL444_ReadyforAutoDem = false;
    };

    this.onEnterShutdown = function () {
        this.log(1, "ENTERING STATE: Shutdown");
        this.stopTimer = 0;
        this.SSL.SSL448_ModuleisDemanded = false;
    };

    this.onEnterFault = function () {
        this.log(1, "ENTERING STATE: Fault");
        this.resetOutputs();
    };

    this.onEnterFastTransfer = function () {
        this.log(1, "ENTERING STATE: FastTransfer");
        this.SSL.SSL429_GenCBClosed = false;
        this.SSL.SSL430_GenCBOpen = true;
        this.SimulatedFrequency = this.NominalFrequency;
        this.SimulatedVoltage = this.ExcitedVoltage;
        this.SimulatedActivePower = 0;
        this.SimulatedReactivePower = 0;
    };

    // Track previous state for manual detection
    //this.previousSmState = this.sm.State;






}



    
    
// Logging helper for debugging
GeneratorController.prototype.log = function (level, message) {
    if (level <= _verbose) {
        var timestamp = new Date().toISOString();
        var state = stateName[this.state];
        try {
            print('[' + timestamp + '] [GenSim ' + this.id + '] [' + state + '] ' + message);
        } catch (error) {
            print('Logging failed for Gen ' + this.id + ': ' + error.message);
        }
    }
};

// Ramps a value toward a target by 'rate' per second
// - If failRampFlag is true, value is frozen (no ramp).
// Modified ramp function with proper bounds checking
GeneratorController.prototype.ramp = function (value, target, rate, failFlag, paramType) {
    var oldValue = value; // Store original value

    if (failFlag) {
        return value;
    }

    var delta = rate * this.dt / 1000.0; // this.dt is ms per cycle
    var newValue;

    if (value < target) {
        newValue = Math.min(target, value + delta);
    } else if (value > target) {
        newValue = Math.max(target, value - delta);
    } else {
        newValue = value; // No change
    }

    // Apply bounds checking based on parameter type
    var finalValue = newValue;
    if (paramType === 'power') {
        finalValue = Math.min(Math.max(newValue, 0), this.NominalPower);
    } else if (paramType === 'voltage') {
    finalValue = Math.min(Math.max(newValue, 0), this.ExcitedVoltage);
    } else if (paramType === 'frequency') {
        finalValue = Math.min(Math.max(newValue, 0), this.NominalFrequency * 1.1); // Allow 10% overfrequency
    }

    if (oldValue !== finalValue) {
        this.log(4, "VARIABLE RAMP: " + paramType + " changed from " + oldValue + " to " + finalValue + " (target: " + target + ", rate: " + rate + "/sec)");
    }

    return finalValue;
};


// Parse R192 Modbus register (bitmask) into SSL command flags.
// R192 Command Word Bit Assignments:
// Bit 0: SSL701_DemandModule_CMD
// Bit 1: SSL702_UtilityOperModuleBlocked_CMD
// Bit 2: SSL703_MainsCBClosed_CMD
// Bit 3: SSL704_EnGenBreakerActToDeadBus_CMD
// Bit 4: SSL705_LoadRejectGenCBOpen_CMD
// Bit 5: SSL706_AuxPowSuppSource1_CMD
// Bit 6: SSL707_AuxPowSuppSource2_CMD
// Bit 7: SSL708_ClockPulse_CMD
// Bit 8: SSL709_GenExcitationOff_CMD
// Bit 9: SSL710_OthGCBClosedandExcitOn_CMD
// (Higher bits are currently undefined or unused in this mapping)
GeneratorController.prototype.parseR192 = function (R192_Value) {
    var commandFlagsMap = [
        { bit: 0, name: "SSL701_DemandModule_CMD" },
        { bit: 1, name: "SSL702_UtilityOperModuleBlocked_CMD" },
        { bit: 2, name: "SSL703_MainsCBClosed_CMD" },
        { bit: 3, name: "SSL704_EnGenBreakerActToDeadBus_CMD" },
        { bit: 4, name: "SSL705_LoadRejectGenCBOpen_CMD" },
        { bit: 5, name: "SSL706_AuxPowSuppSource1_CMD" },
        { bit: 6, name: "SSL707_AuxPowSuppSource2_CMD" },
        { bit: 7, name: "SSL708_ClockPulse_CMD" },
        { bit: 8, name: "SSL709_GenExcitationOff_CMD" },
        { bit: 9, name: "SSL710_OthGCBClosedandExcitOn_CMD" }
        // Add more bits here if R192 definition expands
    ];

    for (var i = 0; i < commandFlagsMap.length; i++) {
        var mapping = commandFlagsMap[i];
        var flagName = mapping.name;
        var previousValue = this.SSL[flagName];
        var newValue = ((R192_Value >> mapping.bit) & 1) === 1;

        if (previousValue !== newValue) {
            this.SSL[flagName] = newValue; // Update the SSL flag
            this.log(5, "VARIABLE CHANGE: " + this.id + ".SSL." + flagName + " (from R192, Bit " + mapping.bit + ") changed from " + previousValue + " to " + newValue);
        }
    }
};

// Reset generator outputs and key SSL flags to a defined idle/standstill state.
// This is typically called on entering STANDSTILL or FAULT states.
GeneratorController.prototype.resetOutputs = function () {
    this.log(1, "Executing resetOutputs for " + this.id); // Added log to indicate function execution
    this.SimulatedVoltage = 0.0; // V
    this.SimulatedFrequency = 0;
    this.SimulatedCurrent = 0;
    this.SimulatedActivePower = 0;
    this.SimulatedReactivePower = 0;
    this.rVoltage = 0.0;
    this.SSL.SSL429_GenCBClosed = false;
    this.SSL.SSL430_GenCBOpen = true;
    this.SSL.SSL431_OperOn = false;
    this.SSL.SSL432_OperOff = true;
    this.SSL.SSL444_ReadyforAutoDem = true;
    this.SSL.SSL448_ModuleisDemanded = false;
    this.SSL.SSL547_GenDeexcited = false;
    this.SSL.SSL592_EngineAtStandStill = true;
    this.SSL.SSL550_GenSyncLoadReleas = false;
};


  GeneratorController.prototype.updateState = function () {
    // 1. Check for Auto mode
    if (!this.SSL.SSL427_ServiceSWAuto) {
        return;
    }

    try {
        // 2. STATE ENTRANCE DETECTION
        // Compares the State Machine's current state against the last one we processed
        var currentSmStateName = this.sm.State; 
        
        if (currentSmStateName !== this.lastProcessedState) {
            this.log(2, "STATE TRANSITION: " + (this.lastProcessedState || "NONE") + " -> " + currentSmStateName);

            // Dynamically call the corresponding onEnter function
            // Example: "running" -> "onEnterRunning"
            var funcName = "onEnter" + currentSmStateName.charAt(0).toUpperCase() + currentSmStateName.slice(1);
            
            if (typeof this[funcName] === 'function') {
                this[funcName]();
            } else {
                this.log(2, "WARNING: No entry function defined for state: " + currentSmStateName);
            }

            // Update trackers and numeric indices for telemetry/Modbus
            this.lastProcessedState = currentSmStateName;
            this.state = stateName.indexOf(currentSmStateName);
            this.GeneratorState = this.state;
        }

        // 3. FAULT DETECTION
        if (this.faultDetected && this.sm.State !== "fault") {
            FireTrigger(this.sm, triggers.FAULT_DETECTED);
            return;
        }

        // 4. TIMERS AND RANGE CHECKS
        var voltageInRange = Math.abs(this.SimulatedVoltage - this.rVoltage) < VOLTAGE_EPSILON;
        var frequencyInRange = Math.abs(this.SimulatedFrequency - this.NominalFrequency) < FREQUENCY_EPSILON;
        var isPowerZero = Math.abs(this.SimulatedActivePower) < POWER_EPSILON;

        if (this.sm.State === "starting") {
            this.startTimer += this.dt;
        } else if (this.sm.State === "shutdown") {
            this.stopTimer += this.dt;
        }

        // 5. STATE LOGIC & TRIGGERS
        switch (this.sm.State) {
          
             case "standstill":
                // Start on demand command (SSL701)
                // SSL709 (de-excitation) is optional - used for dead bus startup only
                if (this.SSL.SSL701_DemandModule_CMD) {
                    FireTrigger(this.sm, triggers.DEMAND);
                }
                break;

            case "starting":
                if (!this.SSL.SSL701_DemandModule_CMD) {
                    FireTrigger(this.sm, triggers.SHUTDOWN_REQUEST);
                    break;
                }

                if (voltageInRange) {
                    FireTrigger(this.sm, triggers.VOLTAGE_READY);
                }
                if (frequencyInRange) {
                    FireTrigger(this.sm, triggers.FREQUENCY_READY);
                }

                if ((this.startTimer >= this.StartDelay || this.FailStartTime) &&
                    voltageInRange && frequencyInRange) {

                    // Determine if bus is live (other generators already connected)
                    var busIsLive = this.SSL.SSL710_OthGCBClosedandExcitOn_CMD;
                    
                     if (this.SSL.SSL709_GenExcitationOff_CMD) {
                       this.SSL.SSL448_ModuleisDemanded = true;
                       this.SSL.SSL547_GenDeexcited = true;
                       this.SSL.SSL550_GenSyncLoadReleas = true;
                      }

                    // SCENARIO 1: Dead bus - first generator closes to dead busbar via SSL704
                    if (this.SSL.SSL704_EnGenBreakerActToDeadBus_CMD && !busIsLive && this.SSL.SSL430_GenCBOpen) {
                        this.SSL.SSL429_GenCBClosed = true;
                        this.SSL.SSL430_GenCBOpen = false;
                        this.SSL.SSL431_OperOn = true;
                        this.SSL.SSL432_OperOff = false;

                        this.log(2, "CB CLOSED to dead busbar (SSL704)");
                        FireTrigger(this.sm, triggers.START_COMPLETE);
                    }

                    // SCENARIO 2: Live bus - automatic synchronization for additional generators
                    if (busIsLive && !this.SSL.SSL709_GenExcitationOff_CMD && this.SSL.SSL430_GenCBOpen) {
                        // Activate synchronization flag
                        this.SSL.SSL441_SyncGenActivated = true;
                        this.SSL.SSL547_GenDeexcited = false;
                        this.SSL.SSL3630_ReleaseLoadAfterGenExcit = true;

                        // Perform automatic synchronization check
                        // Voltage and frequency already checked above
                        // In real implementation, phase angle check would be here
                        var phaseAngleOK = true; // Simplified - assume phase is OK

                        if (phaseAngleOK) {
                            this.SSL.SSL429_GenCBClosed = true;
                            this.SSL.SSL430_GenCBOpen = false;
                            this.SSL.SSL431_OperOn = true;
                            this.SSL.SSL432_OperOff = false;
                            this.log(2, "CB CLOSED via auto-sync to live busbar (SSL441)");
                            FireTrigger(this.sm, triggers.START_COMPLETE);
                        }
                        // SCENARIO 3: Demand off in test mode

                    }
                }
                break;

            case "running":

                if (this.SSL.SSL705_LoadRejectGenCBOpen_CMD) {
                    FireTrigger(this.sm, triggers.TRANSFER_REQUEST);
                // } else if (!this.SSL.SSL701_DemandModule_CMD && this.SSL.SSL710_OthGCBClosedandExcitOn_CMD) {
                } else if (!this.SSL.SSL701_DemandModule_CMD) {//} &&  !this.SSL.SSL710_OthGCBClosedandExcitOn_CMD) {
                    FireTrigger(this.sm, triggers.SHUTDOWN_REQUEST);
                }
                  

                
                break;

            case "shutdown":
                // Per flowchart: open CB when power drops below 10%
                var powerBelow10Percent = this.SimulatedActivePower < (this.NominalPower * 0.1); //  

                // Open CB when power drops below 10% during shutdown
                if (powerBelow10Percent && this.SSL.SSL429_GenCBClosed) {
                    this.SSL.SSL429_GenCBClosed = false;
                    this.SSL.SSL430_GenCBOpen = true;
                    this.SSL.SSL448_ModuleisDemanded = false;
                    this.SSL.SSL431_OperOn = false;
                    this.SSL.SSL432_OperOff = true; 

                    this.log(2, "CB OPENED - power below 10% (" + this.SimulatedActivePower.toFixed(1) + " kW)");
                }

                // Transition to standstill when power reaches zero and stop delay completes
                if (isPowerZero && this.stopTimer >= this.StopDelay) {
                    this.log(2, "Shutdown complete - transitioning to standstill");
                    FireTrigger(this.sm, triggers.POWER_ZERO);
                }
                break;

            case "fastTransfer":
                
                  if (this.SSL.SSL429_GenCBClosed ) {
                   
                   this.SSL.SSL429_GenCBClosed = false;
                   this.SSL.SSL430_GenCBOpen   = true;
                 }
                    
                    
                   if (!this.SSL.SSL705_LoadRejectGenCBOpen_CMD ) {//&& this.SSL.SSL710_OthGCBClosedandExcitOn_CMD) {
                  
                     this.SSL.SSL429_GenCBClosed = true;
                     this.SSL.SSL430_GenCBOpen = false;
                     FireTrigger(this.sm, triggers.DEMAND);

                }
                break;
        }

        // 6. FINAL TELEMETRY SYNC
        // Ensures this.state index is always updated if FireTrigger changed the SM state above
        this.state = stateName.indexOf(this.sm.State);
        this.GeneratorState = this.state;

    } catch (error) {
        this.log(2, "ERROR in updateState: " + error.message);
        FireTrigger(this.sm, triggers.FAULT_DETECTED);
    }
};
  
  // Helper function to set Modbus tag value if it has changed, and log the write.
// Added error handling to SetTagValue
GeneratorController.prototype.setModbusTagChanged = function (registerName, value, isBitmask) {
    var tagPath = this.path + registerName;
    if (this.previousModbusValues[tagPath] !== value || this.previousModbusValues[tagPath] === undefined) {
        var logMessage = "MODBUS WRITE: " + tagPath + " = " + value;
        if (isBitmask) {
            logMessage += " (Hex: " + value.toString(16) + ")";
        }
        this.log(3, logMessage);
        this.previousModbusValues[tagPath] = value;
        try {
            SetTagValue(tagPath, value);
        } catch (error) {
            this.log(2, "ERROR writing to Modbus: " + error.message);
        }
    }
};
// Writes current simulation data to Modbus registers
GeneratorController.prototype.writeModbus = function () {
    // Write simulated measurements to Modbus holding registers
    this.setModbusTagChanged("R129", this.SimulatedActivePower, false);    // Active Power (kW)
    this.setModbusTagChanged("R130", this.SimulatedReactivePower, false); // Reactive Power (kVAr) - Corrected comment unit
    this.setModbusTagChanged("R076", this.SimulatedFrequency * 100, false); // Frequency (0.1 Hz)
    this.setModbusTagChanged("R077", this.SimulatedCurrent, false);       // Current (A)
    this.setModbusTagChanged("R078", this.SimulatedVoltage, false);       // Voltage (V)

    // Write key status bits to R014 status register as a bitmask
    // R014 Bit Assignments (Complete 16-bit mapping according to Innio Interface List):
    // Bit 0 (1): ServiceSWOff
    // Bit 1 (2): ServiceSWManual
    // Bit 2 (4): ServiceSWAuto
    // Bit 3 (8): ReadyforAutoDem
    // Bit 4 (16): GenCBClosed
    // Bit 5 (32): GenCBOpen
    // Bit 6 (64): OperOn
    // Bit 7 (128): OperOff
    // Bit 8 (256): OperEngineisRunning
    // Bit 9 (512): SyncGenActivated
    // Bit 10 (1024): MainsCBClosed
    // Bit 11 (2048): GeneralTrip
    // Bit 12 (4096): TurboChUnitGeneralTrip
    // Bit 13 (8192): TurboChUnitGeneralWarn
    // Bit 14 (16384): IgnSysGeneralTrip
    // Bit 15 (32768): IgnSysGeneralWarn
    var R014 = 0;
    if (this.SSL.SSL425_ServiceSWOff) R014 |= (1 << 0);        // 1
    if (this.SSL.SSL426_ServiceSWManual) R014 |= (1 << 1);      // 2
    if (this.SSL.SSL427_ServiceSWAuto) R014 |= (1 << 2);         // 4
    //if (this.SSL.SSL444_ReadyforAutoDem) R014 |= (1 << 3);      // 8
    if (this.SSL.SSL429_GenCBClosed) R014 |= (1 << 4);          // 16
    if (this.SSL.SSL430_GenCBOpen) R014 |= (1 << 5);            // 32
    if (this.SSL.SSL431_OperOn) R014 |= (1 << 6);               // 64
    if (this.SSL.SSL432_OperOff) R014 |= (1 << 7);              // 128
    if (this.SSL.SSL449_OperEngineisRunning) R014 |= (1 << 8);  // 256
    if (this.SSL.SSL441_SyncGenActivated) R014 |= (1 << 9);     // 512
    if (this.SSL.SSL435_MainsCBClosed) R014 |= (1 << 10);       // 1024
    if (this.SSL.SSL452_GeneralTrip) R014 |= (1 << 11);         // 2048
    if (this.SSL.SSL437_TurboChUnitGeneralTrip) R014 |= (1 << 12); // 4096
    if (this.SSL.SSL438_TurboChUnitGeneralWarn) R014 |= (1 << 13); // 8192
    if (this.SSL.SSL439_IgnSysGeneralTrip) R014 |= (1 << 14);   // 16384
    if (this.SSL.SSL440_IgnSysGeneralWarn) R014 |= (1 << 15);   // 32768
    this.setModbusTagChanged("R014", R014, true);

    // Write SSL statuses to R015
    // R015 Bit Assignments:
    // Bit 0 (1): SyncGenActivated
    // Bit 2 (4): EngineInStartingPhase
    // Bit 3 (8): ReadyforAutoDem
    // Bit 4 (16): DemandforAux
    // Bit 7 (128): ModuleisDemanded
    // Bit 8 (256): OperEngineisRunning
    // Bit 11 (2048): GeneralTrip
    // Bit 12 (4096): GeneralWarn
    var R015 = 0;
    if (this.SSL.SSL441_SyncGenActivated) R015 |= (1 << 0);  // 1
    if (this.SSL.SSL443_EngineInStartingPhase) R015 |= (1 << 2);  // 4
    if (this.SSL.SSL444_ReadyforAutoDem) R015 |= (1 << 3);   // 8
    if (this.SSL.SSL445_DemandforAux) R015 |= (1 << 4);    // 16
    if (this.SSL.SSL448_ModuleisDemanded) R015 |= (1 << 7);  // 128
    if (this.SSL.SSL449_OperEngineisRunning) R015 |= (1 << 8); // 256
    if (this.SSL.SSL452_GeneralTrip) R015 |= (1 << 11); // 2048
    if (this.SSL.SSL453_GeneralWarn) R015 |= (1 << 12); // 4096
    this.setModbusTagChanged("R015", R015, true);

    // Write status bits to R023
    // R023 Bit Assignments:
    // Bit 12 (4096): ReadyforFastStart
    // Bit 15 (32768): ModuleLockedOut
    var R023 = 0;
    if (this.SSL.SSL563_ReadyforFastStart) R023 |= (1 << 12); // 4096
    if (this.SSL.SSL564_ModuleLockedOut) R023 |= (1 << 15); // 32768
    this.setModbusTagChanged("R023", R023, true);

    // Write emergency and auxiliary conditions to R029
    // R029 Bit Assignments:
    // Bit 3 (8): EmergStopPBEngRoom
    // Bit 4 (16): EmergStopPBEngVentRoom
    // Bit 5 (32): EmergStopPBLVMVCtrlRoom
    // Bit 6 (64): EmergStopPBExtCustom
    // Bit 7 (128): AuxSupplySource1
    // Bit 8 (256): AuxSupplySource2
    // Bit 15 (32768): TrAppPowExceeded
    var R029 = 0;
    if (this.SSL.SSL3612_EmergStopPBEngRoom) R029 |= (1 << 3);    // 8
    if (this.SSL.SSL3613_EmergStopPBEngVentRoom) R029 |= (1 << 4);  // 16
    if (this.SSL.SSL3614_EmergStopPBLVMVCtrlRoom) R029 |= (1 << 5); // 32
    if (this.SSL.SSL3615_EmergStopPBExtCustom) R029 |= (1 << 6);  // 64
    if (this.SSL.SSL3616_AuxSupplySource1) R029 |= (1 << 7);    // 128
    if (this.SSL.SSL3617_AuxSupplySource2) R029 |= (1 << 8);    // 256
    if (this.SSL.SSL3624_TrAppPowExceeded) R029 |= (1 << 15);   // 32768
    this.setModbusTagChanged("R029", R029, true);

    // Write thermal and condensation-related statuses to R030
    // R030 Bit Assignments:
    // Bit 0 (1): EngSmoothLoadRejectStart
    // Bit 1 (2): LoadRejWaitforReleaseSync
    // Bit 2 (4): GenAntiCondensHeatInOper
    // Bit 5 (32): ReleaseLoadAfterGenExcit
    var R030 = 0;
    if (this.SSL.SSL3625_EngSmoothLoadRejectStart) R030 |= (1 << 0); // 1
    if (this.SSL.SSL3626_LoadRejWaitforReleaseSync) R030 |= (1 << 1); // 2
    if (this.SSL.SSL3627_GenAntiCondensHeatInOper) R030 |= (1 << 2); // 4
    if (this.SSL.SSL3630_ReleaseLoadAfterGenExcit) R030 |= (1 << 5); // 32
    this.setModbusTagChanged("R030", R030, true);

    // Write engine idle conditions to R031
    // R031 Bit Assignments:
    // Bit 1 (2): EngineAtStandStill
    // Bit 2 (4): ScaveningInOper
    var R031 = 0;
    if (this.SSL.SSL592_EngineAtStandStill) R031 |= (1 << 1); // 2
    if (this.SSL.SSL593_ScaveningInOper) R031 |= (1 << 2); // 4
    this.setModbusTagChanged("R031", R031, true);

    // Write blocking and alarm flags to R109
    // R109 Bit Assignments:
    // Bit 0 (1): UtilityOperModuleBlocked
    // Bit 1 (2): GenBreakerOpenFail
    // Bit 2 (4): GenDeexcited
    // Bit 3 (8): PowerReductionActivated
    // Bit 4 (16): LoadRejectedGCBOpen
    // Bit 5 (32): GenSyncLoadReleas
    var R109 = 0;
    if (this.SSL.SSL545_UtilityOperModuleBlocked) R109 |= (1 << 0); // 1
    if (this.SSL.SSL546_GenBreakerOpenFail) R109 |= (1 << 1);   // 2
    if (this.SSL.SSL547_GenDeexcited) R109 |= (1 << 2);     // 4
    if (this.SSL.SSL548_PowerReductionActivated) R109 |= (1 << 3); // 8
    if (this.SSL.SSL549_LoadRejectedGCBOpen) R109 |= (1 << 4);   // 16
    if (this.SSL.SSL550_GenSyncLoadReleas) R109 |= (1 << 5);   // 32
    this.setModbusTagChanged("R109", R109, true);
};


// Add SSL flag validation method
GeneratorController.prototype.validateSSLFlags = function () {
    // Service switch mutual exclusion (three-way: AUTO, MANUAL, OFF)
    // Only one of these three can be true at any time
    // Priority order if multiple are true: AUTO > MANUAL > OFF
    var serviceModesActive = 0;
    if (this.SSL.SSL427_ServiceSWAuto) serviceModesActive++;
    if (this.SSL.SSL426_ServiceSWManual) serviceModesActive++;
    if (this.SSL.SSL425_ServiceSWOff) serviceModesActive++;

    // If more than one is active, enforce priority: AUTO > MANUAL > OFF
    if (serviceModesActive > 1) {
        if (this.SSL.SSL427_ServiceSWAuto) {
            // AUTO takes priority - turn off others
            this.SSL.SSL426_ServiceSWManual = false;
            this.SSL.SSL425_ServiceSWOff = false;
        } else if (this.SSL.SSL426_ServiceSWManual) {
            // MANUAL takes priority over OFF
            this.SSL.SSL427_ServiceSWAuto = false;
            this.SSL.SSL425_ServiceSWOff = false;
        } else if (this.SSL.SSL425_ServiceSWOff) {
            // OFF is active, turn off others
            this.SSL.SSL427_ServiceSWAuto = false;
            this.SSL.SSL426_ServiceSWManual = false;
        }
    } else if (serviceModesActive === 0) {
        // If none are active, default to AUTO mode for safety
        this.SSL.SSL427_ServiceSWAuto = true;
    }


    // Circuit breaker mutual exclusion
    //if (this.SSL.SSL429_GenCBClosed) {
    //    this.SSL.SSL430_GenCBOpen = false;
    //} else if (this.SSL.SSL430_GenCBOpen) {
    //    this.SSL.SSL429_GenCBClosed = false;
    //}
  // Circuit breaker mutual exclusion - prioritize OPEN for safety
    if (this.SSL.SSL430_GenCBOpen) {
        this.SSL.SSL429_GenCBClosed = false;
    } else if (this.SSL.SSL429_GenCBClosed) {
        this.SSL.SSL430_GenCBOpen = false;
    } else {
        // If neither is set, default to open for safety
        this.SSL.SSL430_GenCBOpen = true;
        this.SSL.SSL429_GenCBClosed = false;
    }
      

    // Operation status mutual exclusion
    if (this.SSL.SSL431_OperOn) {
        this.SSL.SSL432_OperOff = false;
    } else if (this.SSL.SSL432_OperOff) {
        this.SSL.SSL431_OperOn = false;
    }

    // Engine state consistency
    if (this.SSL.SSL592_EngineAtStandStill) {
        this.SSL.SSL449_OperEngineisRunning = false;
        this.SSL.SSL443_EngineInStartingPhase = false;
    }

    // Trip and warning consistency
    if (this.SSL.SSL437_TurboChUnitGeneralTrip ||
        this.SSL.SSL439_IgnSysGeneralTrip ||
        this.SSL.SSL452_GeneralTrip) {
        this.SSL.SSL444_ReadyforAutoDem = false;
        this.SSL.SSL563_ReadyforFastStart = false;
    }

    // Emergency stop handling
    if (this.SSL.SSL3612_EmergStopPBEngRoom ||
        this.SSL.SSL3613_EmergStopPBEngVentRoom ||
        this.SSL.SSL3614_EmergStopPBLVMVCtrlRoom ||
        this.SSL.SSL3615_EmergStopPBExtCustom) {
        this.SSL.SSL431_OperOn = false;
        this.SSL.SSL432_OperOff = true;
        this.SSL.SSL444_ReadyforAutoDem = false;
        this.SSL.SSL448_ModuleisDemanded = false;
    }

    // Auxiliary power supply mutual exclusion
    if (this.SSL.SSL3616_AuxSupplySource1) {
        this.SSL.SSL3617_AuxSupplySource2 = false;
    } else if (this.SSL.SSL3617_AuxSupplySource2) {
        this.SSL.SSL3616_AuxSupplySource1 = false;
    }

    // Load rejection and synchronization
    if (this.SSL.SSL549_LoadRejectedGCBOpen) {
        this.SSL.SSL550_GenSyncLoadReleas = false;
        this.SSL.SSL448_ModuleisDemanded = true;
    }

    // Module lockout handling
    if (this.SSL.SSL564_ModuleLockedOut) {
        this.SSL.SSL444_ReadyforAutoDem = false;
        this.SSL.SSL563_ReadyforFastStart = false;
        this.SSL.SSL448_ModuleisDemanded = false;
    }

    // Command flag relationships
    if (this.SSL.SSL709_GenExcitationOff_CMD) {
        this.SSL.SSL547_GenDeexcited = true;
    } else {
        this.SSL.SSL547_GenDeexcited = false; // Ensure it reflects command OFF state
    }

    if (this.SSL.SSL705_LoadRejectGenCBOpen_CMD) {
        this.SSL.SSL549_LoadRejectedGCBOpen = true;
    }   else {  
        this.SSL.SSL549_LoadRejectedGCBOpen = false; // Ensure it reflects command OFF state
    }

    // // Update operation status based on commands
    // if (this.SSL.SSL701_DemandModule_CMD && !this.SSL.SSL564_ModuleLockedOut) {
    //     this.SSL.SSL448_ModuleisDemanded = true;
    // }
};

// Modified updateSimulationDynamics to use the new ramp function
GeneratorController.prototype.updateSimulationDynamics = function () {
    // Determine target voltage (rVoltage) based on state and excitation status
    if (this.sm.State === 'standstill' || this.sm.State === 'fault') {
        this.rVoltage = 0.0;
    } else if (this.sm.State === 'starting') {
        if (this.SSL.SSL547_GenDeexcited) { // If commanded to be de-excited
            this.rVoltage = this.DeExcitedVoltage;
        } else { // Excitation is allowed/commanded ON
            // If nearly at or past de-excited voltage, target excited voltage. Otherwise, keep targeting de-excited.
            if (Math.abs(this.SimulatedVoltage - this.DeExcitedVoltage) < VOLTAGE_EPSILON || this.SimulatedVoltage > this.DeExcitedVoltage) {
                this.rVoltage = this.ExcitedVoltage;
            } else {
                this.rVoltage = this.DeExcitedVoltage;
            }
        }
    } else if (this.sm.State === 'running') {
        // Per flowchart: de-excited generators run at <3kV (DeExcitedVoltage), not 0V
        this.rVoltage = this.SSL.SSL547_GenDeexcited ? this.DeExcitedVoltage : this.ExcitedVoltage;
    } else if (this.sm.State === 'shutdown') {
        // During shutdown, always ramp voltage to 0, regardless of excitation SSL flag.
        this.rVoltage = 0.0;
    } else if (this.sm.State === 'fastTransfer') {
        // In fastTransfer, target excited voltage
        this.rVoltage = this.ExcitedVoltage;
    }

    this.SimulatedVoltage = this.ramp(this.SimulatedVoltage, this.rVoltage, this.RampRateVoltage, this.FailRampUp, 'voltage');

    // Frequency Ramping Logic
    var targetFrequency = 0.0;
    if (this.sm.State === 'starting' || this.sm.State === 'running' || this.sm.State === 'fastTransfer') {
        targetFrequency = this.NominalFrequency;
    } else if (this.sm.State === 'shutdown') {
        targetFrequency = 0.0; // Ramp frequency down during shutdown
    }

    this.SimulatedFrequency = this.ramp(this.SimulatedFrequency, targetFrequency, this.RampRateFrequency, this.FailRampUp, 'frequency');
    
    // Ensure hard zero if in terminal states
    if (this.sm.State === 'standstill' || this.sm.State === 'fault') {
        this.SimulatedFrequency = 0.0;
    }

    // Power Ramping Logic
    var targetPower = 0.0;
    // Only allow target power if running and CB is closed.
    if (this.sm.State === 'running' && this.SSL.SSL429_GenCBClosed) {
        targetPower = this.rSetpointPower;
    } else if (this.sm.State === 'fastTransfer') { // Explicitly target zero power during fast transfer
        targetPower = 0.0;
    }

    var currentPowerRampRate = (this.SimulatedActivePower > targetPower && targetPower === 0.0) ? this.RampRatePowerDown : this.RampRatePowerUp;
    var failRampFlag = (this.SimulatedActivePower > targetPower && targetPower === 0.0) ? this.FailRampDown : this.FailRampUp;
    if (this.sm.State === 'shutdown') { // Ensure ramp down rate and flag for shutdown
        currentPowerRampRate = this.RampRatePowerDown;
        failRampFlag = this.FailRampDown;
    }

    this.SimulatedActivePower = this.ramp(this.SimulatedActivePower, targetPower, currentPowerRampRate, failRampFlag, 'power');

    // Ensure hard zero if CB is open (unless starting) or in terminal states.
    if ((this.SSL.SSL430_GenCBOpen && this.sm.State !== 'starting') || this.sm.State === 'standstill' || this.sm.State === 'fault') {
        this.SimulatedActivePower = 0.0;
    }

    // Reactive Power Ramping Logic
    var targetReactivePower = 0.0;
    // Only allow target reactive power if running and CB is closed.
    if (this.sm.State === 'running' && this.SSL.SSL429_GenCBClosed) {
        targetReactivePower = this.rSetpointReactivePower;
    } else if (this.sm.State === 'fastTransfer') { // Explicitly target zero reactive power
        targetReactivePower = 0.0;
    }

    var currentReactivePowerRampRate = (this.SimulatedReactivePower > targetReactivePower && targetReactivePower === 0.0) ? this.RampRatePowerDown : this.RampRatePowerUp;
    var failReactiveRampFlag = (this.SimulatedReactivePower > targetReactivePower && targetReactivePower === 0.0) ? this.FailRampDown : this.FailRampUp;
    if (this.sm.State === 'shutdown') {
        currentReactivePowerRampRate = this.RampRatePowerDown;
        failReactiveRampFlag = this.FailRampDown;
    }
    
    this.SimulatedReactivePower = this.ramp(this.SimulatedReactivePower, targetReactivePower, currentReactivePowerRampRate, failReactiveRampFlag, 'power');

    if ((this.SSL.SSL430_GenCBOpen && this.sm.State !== 'starting') || this.sm.State === 'standstill' || this.sm.State === 'fault') {
        this.SimulatedReactivePower = 0.0;
    }

    // Current calculation based on Active (P) and Reactive (Q) Power
    var P_kW = this.SimulatedActivePower;
    var Q_kVAr = this.SimulatedReactivePower;
    var S_kVA = Math.sqrt(P_kW * P_kW + Q_kVAr * Q_kVAr); // Apparent power in kVA

    if (this.SimulatedVoltage > VOLTAGE_EPSILON) {
        // I = S / (sqrt(3) * V_L)
        // S is in kVA, V_L is in Volts. To get Amps, S_kVA * 1000
        this.SimulatedCurrent = (S_kVA * 1000) / (this.SimulatedVoltage * 1.732);
    } else {
        this.SimulatedCurrent = 0.0;
    }
    this.SimulatedCurrent = parseFloat(this.SimulatedCurrent.toFixed(2)); // Round to 2 decimal places
};

// Update the tick method to include SSL validation and top-level error handling
GeneratorController.prototype.tick = function () {
    try {
        // Log rSetpointPower change if it occurred
        if (this.rSetpointPower !== this.previousSetpointPower) {
            this.log(4, "VARIABLE CHANGE: " + this.id + ".rSetpointPower changed from " + this.previousSetpointPower + " kW to " + this.rSetpointPower + " kW");
            this.previousSetpointPower = this.rSetpointPower; // Update previous value
        }
        // Log rSetpointReactivePower change if it occurred
        // Assuming this.previousSetpointReactivePower was initialized, e.g., in constructor or similar to previousSetpointPower
        // Initialization for it.
        if (this.rSetpointReactivePower !== this.previousSetpointReactivePower) {
            this.log(4, "VARIABLE CHANGE: " + this.id + ".rSetpointReactivePower changed from " + this.previousSetpointReactivePower + " kVAr to " + this.rSetpointReactivePower + " kVAr");
            this.previousSetpointReactivePower = this.rSetpointReactivePower; // Update previous value
        }

        this.updateSimulationDynamics(); // Process simulation physics and ramping

        // Read simulation fault control flags from Modbus Register R950
        // R950 Bit Assignments:
        // Bit 0: SimulateFailToStart
        // Bit 1: FailRampUp
        // Bit 2: FailRampDownR950
        // Bit 3: FailStartTime
        // Bit 4: ResetFaultCMD
        var R950_Value = GetTagValue(this.path + "R950");

        var newSimulateFailToStart = ((R950_Value >> 0) & 1) === 1;
        if (this.SimulateFailToStart !== newSimulateFailToStart) {
            this.log(4, "VARIABLE CHANGE: " + this.id + ".SimulateFailToStart (from R950, Bit 0) changed from " + this.SimulateFailToStart + " to " + newSimulateFailToStart);
            this.SimulateFailToStart = newSimulateFailToStart;
        }

        var newFailRampUp = ((R950_Value >> 1) & 1) === 1;
        if (this.FailRampUp !== newFailRampUp) {
            this.log(4, "VARIABLE CHANGE: " + this.id + ".FailRampUp (from R950, Bit 1) changed from " + this.FailRampUp + " to " + newFailRampUp);
            this.FailRampUp = newFailRampUp;
        }

        var newFailRampDown = ((R950_Value >> 2) & 1) === 1;
        if (this.FailRampDown !== newFailRampDown) {
            this.log(4, "VARIABLE CHANGE: " + this.id + ".FailRampDown (from R950, Bit 2) changed from " + this.FailRampDown + " to " + newFailRampDown);
            this.FailRampDown = newFailRampDown;
        }

        var newFailStartTime = ((R950_Value >> 3) & 1) === 1;
        if (this.FailStartTime !== newFailStartTime) {
            this.log(4, "VARIABLE CHANGE: " + this.id + ".FailStartTime (from R950, Bit 3) changed from " + this.FailStartTime + " to " + newFailStartTime);
            this.FailStartTime = newFailStartTime;
        }

        var resetFaultCMD = ((R950_Value >> 4) & 1) === 1; // Renamed to avoid conflict if ResetFault was a class property
        if (resetFaultCMD) {
            this.log(4, "COMMAND: " + this.id + ".resetFaultCMD (from R950, Bit 4) is active (1)");
            if (this.faultDetected) { // Only try to clear if a fault is detected
                this.faultDetected = false; // Clear the fault flag
                FireTrigger(this.sm, triggers.FAULT_CLEARED); // Trigger fault cleared transition
                this.log(2, "FAULT CLEARED for " + this.id + " via R950 command. Triggered FAULT_CLEARED.");
            } else {
                this.log(1, "INFO: " + this.id + ".resetFaultCMD (from R950, Bit 4) is active, but no fault was detected.");
            }
        }

        // Read main command word from Modbus Register R192 and parse into SSL flags
        var R192_Value = GetTagValue(this.path + "R192");
        this.parseR192(R192_Value);

        // Validate SSL flags to ensure consistency before updating the state machine
        this.validateSSLFlags();

        // step the state
        this.updateState();

        // write outputs
        this.writeModbus();

        // Generator Circuit Breaker Closing Logic based on SSL703 command
        if (this.sm.State === 'running' && this.SSL.SSL703_MainsCBClosed_CMD && this.SSL.SSL430_GenCBOpen) {
            // Simplified synchronization check:
            // Assumes being in 'running' state means voltage & frequency should be near nominal.
            // ExcitedVoltage is the nominal voltage target.
            var voltageReadyForSync = Math.abs(this.SimulatedVoltage - this.ExcitedVoltage) < VOLTAGE_EPSILON;
            var frequencyReadyForSync = Math.abs(this.SimulatedFrequency - this.NominalFrequency) < FREQUENCY_EPSILON;

            if (voltageReadyForSync && frequencyReadyForSync) {
                this.log(2, "COMMAND: Closing Gen CB (" + this.id + ") due to SSL703_MainsCBClosed_CMD and sync conditions met.");
                var oldSSL429 = this.SSL.SSL429_GenCBClosed;
                var oldSSL430 = this.SSL.SSL430_GenCBOpen;

                this.SSL.SSL429_GenCBClosed = true;
                this.SSL.SSL430_GenCBOpen = false;

                if (oldSSL429 !== this.SSL.SSL429_GenCBClosed) {
                    this.log(4, "VARIABLE CHANGE: " + this.id + ".SSL.SSL429_GenCBClosed changed from " + oldSSL429 + " to " + this.SSL.SSL429_GenCBClosed);
                }
                if (oldSSL430 !== this.SSL.SSL430_GenCBOpen) {
                    this.log(4, "VARIABLE CHANGE: " + this.id + ".SSL.SSL430_GenCBOpen changed from " + oldSSL430 + " to " + this.SSL.SSL430_GenCBOpen);
                }

            } else {
                // Log that command is present but conditions are not met
                this.log(1, "INFO: SSL703_MainsCBClosed_CMD (" + this.id + ") is true, but sync conditions not met for CB close. V_sim: " + this.SimulatedVoltage.toFixed(2) + " (Target: " + this.ExcitedVoltage.toFixed(2) + "), F_sim: " + this.SimulatedFrequency.toFixed(2) + " (Target: " + this.NominalFrequency.toFixed(2) + ")");
            }
        }

        // Per flowchart: Detect SSL710 rising edge -> open 7-second window for additional generators
        // "after 2 second the scada controller send a command SSL710 = 1. Generator in idle operation 
        // (without load) and de-excited generator (<3kV) and closing their breakers. during 7 second."
        if (!this.ssl710PreviousValue && this.SSL.SSL710_OthGCBClosedandExcitOn_CMD) {
          this.deadBusWindowTimer = 3000; // Start 3-second window
          this.log(2, "SSL710 rising edge detected - 3s dead bus window opened for " + this.id);
        }
        this.ssl710PreviousValue = this.SSL.SSL710_OthGCBClosedandExcitOn_CMD;

        // During the 7-second window: allow de-excited generators in running state to close CB
        if (this.deadBusWindowTimer > 0) {
            this.deadBusWindowTimer -= this.dt;

            if (this.sm.State === 'running' &&
                this.SSL.SSL430_GenCBOpen &&
                this.SSL.SSL547_GenDeexcited &&
                this.SSL.SSL704_EnGenBreakerActToDeadBus_CMD) {

                this.SSL.SSL429_GenCBClosed = true;
                this.SSL.SSL430_GenCBOpen = false;
                this.log(2, "CB CLOSED during 7s dead bus window (de-excited) for " + this.id);
            }
        }



    } catch (error) {
        // Catch any unhandled error within the generator's tick, log it, and attempt to go to a FAULT state.
        var stack = error.stack ? error.stack : "No stack available";
        this.log(2, "CRITICAL ERROR in " + this.id + ".tick(): " + error.message + "\nStack: " + stack);
        this.faultDetected = true;

        // Try to transition the state machine to FAULT state.
        // This might not always succeed if the state machine itself or FireTrigger is compromised,
        // but it's the best effort. resetOutputs() will be called by the on-enter logic for FAULT.
        if (this.sm.State !== "fault") {
            try {
                FireTrigger(this.sm, triggers.FAULT_DETECTED);
            } catch (smError) {
                this.log(2, "Error trying to fire FAULT_DETECTED trigger for " + this.id + ": " + smError.message);
                // If firing trigger fails, manually call resetOutputs as a fallback to ensure safe state.
                this.resetOutputs();
            }
        } else {
            // Already in fault state, ensure outputs are reset if something went wrong after entering fault.
            this.resetOutputs();
        }

        // Attempt to update Modbus with the fault state, if possible.
        try {
            this.writeModbus();
        } catch (modbusError) {
            this.log(2, "Error trying to write Modbus during critical fault handling for " + this.id + ": " + modbusError.message);
        }
    }
};

// Create and simulate 5 generator instances
// Expanded to simulate 22 generators including 2 swing units across 4 switchgears (GPS1-GPS4)
//(FCB1/FCB2 decide active switchgear)
var generators = [];

// GPS1: G1 to G5
for (var i = 1; i <= 5; i++) generators.push(new GeneratorController("G" + i));
// GPS2: G6 to G10
for (var i = 6; i <= 10; i++) generators.push(new GeneratorController("G" + i));
// GPS3: G11 to G15
for (var i = 11; i <= 15; i++) generators.push(new GeneratorController("G" + i));
// GPS4: G16 to G20
for (var i = 16; i <= 20; i++) generators.push(new GeneratorController("G" + i));

// Swing Generators
// G21 = shared between GPS1 and GPS3 
// G22 = shared between GPS2 and GPS4 
generators.push(new GeneratorController("G21"));
generators.push(new GeneratorController("G22"));

// Central controller per GPS switchgear for load‐sharing
// where total demand is stored (e.g., P74)
function SwitchgearController(id) {
    this.id = id; // e.g., GPS1, GPS2...
    this.path = "/SWG/sMB_GPS" + id.slice(-1) + "/sMB/sMB&&&sMB.sMB.T4.";
    ///SWG/sMB_GPS1/sMB/sMB&&&sMB_GPS1.sMB.T4.P74

    //this.demandPath = "/" + id + "/Demand";
    this.previousOnlineCount = -1; // Initialize for write-on-change logic
}

SwitchgearController.prototype.tick = function (gens) {
    var totalDemand = GetTagValue(this.path + "P74") || 0;


    var onlineGenerators = [];

    for (var i = 0; i < gens.length; i++) {
        var gen = gens[i];
        var assignToThis = false;

        // Generator routing based on custom FCB position logic
        if (["G1", "G2", "G3", "G4", "G5"].indexOf(gen.id) !== -1) {
            if (gen.FCB1 && this.id === "GPS1") assignToThis = true;
            if (gen.FCB2 && this.id === "GPS2") assignToThis = true;
        } else if (["G6", "G7", "G8", "G9", "G10"].indexOf(gen.id) !== -1) {
            if (gen.FCB1 && this.id === "GPS2") assignToThis = true;
            if (gen.FCB2 && this.id === "GPS1") assignToThis = true;
        } else if (["G11", "G12", "G13", "G14", "G15"].indexOf(gen.id) !== -1) {
            if (gen.FCB1 && this.id === "GPS3") assignToThis = true;
            if (gen.FCB2 && this.id === "GPS4") assignToThis = true;
        } else if (["G16", "G17", "G18", "G19", "G20"].indexOf(gen.id) !== -1) {
            if (gen.FCB1 && this.id === "GPS4") assignToThis = true;
            if (gen.FCB2 && this.id === "GPS3") assignToThis = true;
        } else if (gen.id === "G21") {
            if (gen.FCB1 && this.id === "GPS1") assignToThis = true;
            if (gen.FCB2 && this.id === "GPS3") assignToThis = true;
        } else if (gen.id === "G22") {
            if (gen.FCB1 && this.id === "GPS2") assignToThis = true;
            if (gen.FCB2 && this.id === "GPS4") assignToThis = true;
        }

        if (assignToThis && gen.state === 2) {
            onlineGenerators.push(gen);
        }
    }

    var count = onlineGenerators.length;
    var perGenLoad = (count > 0) ? totalDemand / count : 0;
    for (var j = 0; j < onlineGenerators.length; j++) {
        onlineGenerators[j].rSetpointPower = perGenLoad;
    }

    var onlineCount = onlineGenerators.length;
    // Write online count to Modbus only if it has changed
    if (this.previousOnlineCount !== onlineCount) {
        SetTagValue(this.path + "R901", onlineCount); // R901 = number of running generators
        this.previousOnlineCount = onlineCount;

    }
};


var Switchgears = [];
for (var i = 1; i <= 4; i++) Switchgears.push(new SwitchgearController("GPS" + i));

// Main loop
while (true) {
    var currentTime = Date.now();
    var cycleDuration = currentTime - lastLoopTime;

    ProcessScriptEvents(100); // 100 ms cycle

    if (_verbose > 0 && cycleDuration > maxCycleDuration) {
        maxCycleDuration = cycleDuration;


        print('New max cycle duration: ' + maxCycleDuration + 'ms\n');
    }

          // tick and Update switchgear control for load sharing
    for (var g = 0; g < Switchgears.length; g++) {
        try {
            Switchgears[g].tick(generators);
        } catch (e) {
            // Use a generic print for errors here as this is outside generator's log method
            if (_verbose >= 2) print('Error in Switchgear ' + Switchgears[g].id + ' tick: ' + e.message + '\nStack: ' + e.stack);
        }
    }
        
        

   
    // tick and update all generators
    for (var i = 0; i < generators.length; i++) {
        try {
            generators[i].tick();
        } catch (e) {

            // Generator's log method if possible, or fallback
            // 
            if (generators[i] && typeof generators[i].log === 'function') {
                generators[i].log(2, 'ERROR in generator tick: ' + e.message + '\nStack: ' + e.stack);
            } else {
                if (_verbose >= 2) print('Error in Generator ' + (generators[i] ? generators[i].id : 'Unknown') + ' tick: ' + e.message + '\nStack: ' + e.stack);
            }
        }
    }



          lastLoopTime = currentTime;
          
          
          

}


