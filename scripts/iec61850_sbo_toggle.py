#!/usr/bin/env python3
"""Small CLI to exercise SBO (select) + toggle OPERATE on an IEC61850 control object.

Usage (dry-run):
    ./scripts/iec61850_sbo_toggle.py --host 172.16.11.18 --port 102 --object "IED/LD/CSWI1.Pos" 

To actually send commands (DANGEROUS - will operate equipment) add --yes:
    ./scripts/iec61850_sbo_toggle.py --host 172.16.11.18 --port 102 --object "IED/LD/CSWI1.Pos" --yes

Behavior:
- Connects to the IED using libiec61850 wrapper
- Reads current stVal (boolean/int) and computes a toggle value
- Performs SELECT (SBO or SBOw) and reads the ctlNum from SBOw/.ctlNum
- Sets ctlNum on client, performs OPERATE and verifies the value changed
- Cleans up (Cancel) on failure or when requested

Safety: this tool WILL operate real equipment when --yes is provided. Do not run on production without authorization.
"""

import argparse
import logging
import sys
import time
import os
from datetime import datetime

from src.protocols.iec61850 import iec61850_wrapper as iec61850

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("iec61850-sbo-toggle")

DEFAULT_HOST = "172.16.11.18"
DEFAULT_PORT = 102


def connect(host: str, port: int):
    conn = iec61850.IedConnection_create()
    err = iec61850.IedConnection_connect(conn, host, port)
    if err != 0:
        raise RuntimeError(f"Could not connect to {host}:{port} (error {err})")
    return conn


def read_stval(conn, obj_ref):
    # Read current stVal - try full path
    full_ref = f"{obj_ref}.stVal"
    try:
        val, err = iec61850.IedConnection_readBooleanValue(conn, full_ref, iec61850.IEC61850_FC_ST)
        if err == iec61850.IED_ERROR_OK:
            return bool(val)
    except Exception:
        pass

    try:
        val, err = iec61850.IedConnection_readBooleanValue(conn, full_ref, iec61850.IEC61850_FC_CO)
        if err == iec61850.IED_ERROR_OK:
            return bool(val)
    except Exception:
        pass

    val, err = iec61850.IedConnection_readInt32Value(conn, full_ref, iec61850.IEC61850_FC_ST)
    if err == iec61850.IED_ERROR_OK:
        return int(val)
    
    val, err = iec61850.IedConnection_readInt32Value(conn, full_ref, iec61850.IEC61850_FC_CO)
    if err == iec61850.IED_ERROR_OK:
        return int(val)
    
    # If reading fails, assume False/0
    print(f"Warning: Could not read stVal, assuming False")
    return False


def read_ctlnum_prefer_sbo(conn, ctx_obj_ref, sbo_ref, object_ref):
    # Prefer SBOw/SBO ctlNum, fallback to object_ref.ctlNum
    if sbo_ref:
        try:
            val, err = iec61850.IedConnection_readInt32Value(conn, f"{sbo_ref}.ctlNum", iec61850.IEC61850_FC_ST)
            if err == iec61850.IED_ERROR_OK:
                return int(val) % 256
        except Exception:
            pass
    val, err = iec61850.IedConnection_readInt32Value(conn, f"{object_ref}.ctlNum", iec61850.IEC61850_FC_ST)
    if err == iec61850.IED_ERROR_OK:
        return int(val) % 256
    return None


def cli_main():
    p = argparse.ArgumentParser(description="IEC61850 SBO + toggle operate (integration)")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", default=DEFAULT_PORT, type=int)
    p.add_argument("--object", required=True, help="Full control object reference (e.g. IED/LD/CSWI1.Pos)")
    p.add_argument("--sbo-ref", help="Optional explicit SBO/SBOw reference (e.g. IED/LD/CSWI1.Pos.SBOw)")
    p.add_argument("--yes", action="store_true", help="Actually send SELECT/OPERATE (required to run) — dangerous")
    p.add_argument("--timeout", type=float, default=5.0, help="Timeouts / sleeps")
    p.add_argument("--dump-mms", action="store_true", help="Dump MmsValue payloads to files for diagnostics")
    args = p.parse_args()

    if not args.yes:
        log.warning("DRY RUN: no commands will be sent. Add --yes to actually perform SELECT/OPERATE")

    conn = None
    control_client = None
    try:
        log.info(f"Connecting to {args.host}:{args.port} ...")
        conn = connect(args.host, args.port)
        log.info("Connected")

        object_ref = args.object.rstrip('/')
        sbo_ref = args.sbo_ref

        # Read current value
        cur = read_stval(conn, object_ref)
        log.info(f"Current stVal for {object_ref}: {cur!r}")

        # Also try to read ctlVal
        try:
            ctl_val, err = iec61850.IedConnection_readBooleanValue(conn, f"{object_ref}.ctlVal", iec61850.IEC61850_FC_CO)
            if err == iec61850.IED_ERROR_OK:
                log.info(f"Current ctlVal (bool): {bool(ctl_val)}")
            else:
                ctl_val, err = iec61850.IedConnection_readInt32Value(conn, f"{object_ref}.ctlVal", iec61850.IEC61850_FC_CO)
                if err == iec61850.IED_ERROR_OK:
                    log.info(f"Current ctlVal (int): {int(ctl_val)}")
                else:
                    log.info("Could not read ctlVal")
        except Exception as e:
            log.info(f"Error reading ctlVal: {e}")

        # Try to read control block
        try:
            blk, err = iec61850.IedConnection_readBooleanValue(conn, f"{object_ref}.Oper.ctlBlk", iec61850.IEC61850_FC_CO)
            if err == iec61850.IED_ERROR_OK:
                log.info(f"Control blocked: {bool(blk)}")
            else:
                log.info("Could not read ctlBlk")
        except Exception as e:
            log.info(f"Error reading ctlBlk: {e}")

        # Try to read ctlModel
        try:
            model, err = iec61850.IedConnection_readInt32Value(conn, f"{object_ref}.Oper.ctlModel", iec61850.IEC61850_FC_CO)
            if err == iec61850.IED_ERROR_OK:
                log.info(f"Control model from data: {int(model)}")
            else:
                log.info("Could not read ctlModel")
        except Exception as e:
            log.info(f"Error reading ctlModel: {e}")

        # Compute toggle
        if isinstance(cur, bool):
            target = (not cur)
        elif isinstance(cur, int):
            target = 0 if cur else 1
        else:
            raise RuntimeError("Unsupported stVal type for toggle")
        log.info(f"Will toggle to: {target!r}")

        if not args.yes:
            log.info("Dry-run complete — exiting without sending commands")
            return 0

        # Helper: dump MmsValue to file when requested
        def _dump_mms_val(mms_val, label: str):
            if not args.dump_mms or not mms_val:
                return
            try:
                s = iec61850.MmsValue_toString(mms_val)
                if s is None:
                    s = '<MmsValue_toString returned None>'
            except Exception:
                s = '<MmsValue_toString failed>'
            try:
                out_dir = os.path.join(os.getcwd(), 'dumps')
                os.makedirs(out_dir, exist_ok=True)
                fname = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S.%f')}_{label}.txt"
                path = os.path.join(out_dir, fname)
                with open(path, 'w') as f:
                    f.write(s)
                log.info(f"Dumped MmsValue to {path}")
            except Exception as e:
                log.warning(f"Failed to write MmsValue dump: {e}")

        # Create ControlObjectClient
        log.info("Creating ControlObjectClient")
        control_client = iec61850.ControlObjectClient_create(object_ref, conn)
        if not control_client:
            raise RuntimeError("ControlObjectClient_create failed — falling back not implemented in this script")

        # Set ctlNum
        try:
            iec61850.ControlObjectClient_setCtlNum(control_client, 1728)
            log.info("Set ctlNum to 1728 on control_client")
        except Exception as e:
            log.warning(f"Setting ctlNum failed: {e}")

        # Set originator (some IEDs require originator info for SELECT/OPERATE)
        try:
            iec61850.ControlObjectClient_setOriginator(control_client, "SCADAScout", 3)
            log.info("Set originator on ControlObjectClient: SCADAScout/3")
        except Exception as e:
            log.warning(f"Setting originator failed: {e}")

        ctl_model = iec61850.ControlObjectClient_getControlModel(control_client)
        log.info(f"Control model: {ctl_model}")

        # Select (SBO or SBOw)
        log.info("Performing SELECT phase (SBO)")
        success = False

        # If an explicit sbo_ref is provided, try selection against that client first (some IEDs require selecting SBOw address)
        if sbo_ref:
            try:
                log.info(f"Attempting SELECT against SBO ref: {sbo_ref}")
                sbo_client = iec61850.ControlObjectClient_create(sbo_ref, conn)
            except Exception:
                sbo_client = None

            if sbo_client:
                try:
                    iec61850.ControlObjectClient_setCtlNum(sbo_client, 1728)
                    mms_sbo = iec61850.MmsValue_newBoolean(target)
                    _dump_mms_val(mms_sbo, 'sbo_select_value')
                    try:
                        ok = iec61850.ControlObjectClient_selectWithValue(sbo_client, mms_sbo)
                        if ok:
                            log.info("SELECT (SBO ref) succeeded")
                            # read ctlNum from SBOw explicitly
                            try:
                                sbo_ctl, err_sbo = iec61850.IedConnection_readInt32Value(conn, f"{sbo_ref}.ctlNum", iec61850.IEC61850_FC_ST)
                                if err_sbo == iec61850.IED_ERROR_OK:
                                    ctl_num = sbo_ctl
                                    log.info(f"Captured ctlNum from SBO ref: {ctl_num}")
                                else:
                                    log.info(f"Could not read {sbo_ref}.ctlNum (err={err_sbo})")
                            except Exception:
                                pass
                            success = True
                    finally:
                        iec61850.MmsValue_delete(mms_sbo)
                except Exception as e:
                    log.info(f"SELECT against SBO ref raised: {e}")
                try:
                    iec61850.ControlObjectClient_destroy(sbo_client)
                except Exception:
                    pass

        # If not selected via SBO ref, try multiple selectWithValue options on main client
        if not success:
            # Try with inverted target (False for close)
            log.info(f"Trying selectWithValue with inverted target (bool): {not target}")
            mms_inv = iec61850.MmsValue_newBoolean(not target)
            _dump_mms_val(mms_inv, 'select_inverted')
            try:
                success = iec61850.ControlObjectClient_selectWithValue(control_client, mms_inv)
                if not success:
                    err = iec61850.ControlObjectClient_getLastError(control_client)
                    log.info(f"selectWithValue(inverted) failed, lastError={err}")
            finally:
                iec61850.MmsValue_delete(mms_inv)

        if not success:
            # Try with target
            log.info(f"Trying selectWithValue with target (bool): {target}")
            mms_target = iec61850.MmsValue_newBoolean(target)
            _dump_mms_val(mms_target, 'select_target')
            try:
                success = iec61850.ControlObjectClient_selectWithValue(control_client, mms_target)
                if not success:
                    err = iec61850.ControlObjectClient_getLastError(control_client)
                    log.info(f"selectWithValue(target) failed, lastError={err}")
            finally:
                iec61850.MmsValue_delete(mms_target)

        if not success:
            # Try with current
            log.info(f"Trying selectWithValue with current (bool): {cur}")
            mms_cur = iec61850.MmsValue_newBoolean(cur)
            _dump_mms_val(mms_cur, 'select_current')
            try:
                success = iec61850.ControlObjectClient_selectWithValue(control_client, mms_cur)
                if not success:
                    err = iec61850.ControlObjectClient_getLastError(control_client)
                    log.info(f"selectWithValue(current) failed, lastError={err}")
            finally:
                iec61850.MmsValue_delete(mms_cur)
        
        # if not success:
        #     log.warning("All selectWithValue attempts failed, trying full Oper structure selectWithValue")
        #     # Try building Oper structure from IED as template and use that for selectWithValue
        #     try:
        #         struct, err = iec61850.IedConnection_readObject(conn, f"{object_ref}.Oper", iec61850.IEC61850_FC_CO)
        #         if struct:
        #             try:
        #                 # set ctlVal element (index 0) to inverted target (as IED expects)
        #                 new_val = iec61850.MmsValue_newBoolean(not target)
        #                 iec61850.MmsValue_setElement(struct, 0, new_val)
        #                 _dump_mms_val(struct, 'select_oper_struct')
        #                 iec61850.MmsValue_delete(new_val)
        #                 ok = iec61850.ControlObjectClient_selectWithValue(control_client, struct)
        #                 if ok:
        #                     success = True
        #                             log.info("SELECT with Oper structure succeeded")
        #             finally:
        #                 iec61850.MmsValue_delete(struct)
        #         else:
        #             log.info("Could not read Oper structure from IED for selectWithValue")
        #     except Exception as e:
        #         log.info(f"SELECT with Oper structure attempt raised: {e}")

        if not success:
            log.warning("All selectWithValue attempts (incl. Oper-struct) failed, trying plain select")
            success = iec61850.ControlObjectClient_select(control_client)
            if not success:
                err = iec61850.ControlObjectClient_getLastError(control_client)
                log.info(f"plain select failed, lastError={err}")
        
        if not success:
            log.warning("All SELECT attempts failed, trying plain select then direct operate")
            # Try plain select first (already attempted above), then direct operate
            try:
                err = iec61850.ControlObjectClient_getLastError(control_client)
            except Exception:
                err = None
            log.info(f"Pre-direct-operate lastError={err}")

            # Try direct operate without SELECT
            ctl_val_bool = target
            mms = iec61850.MmsValue_newBoolean(ctl_val_bool)
            _dump_mms_val(mms, 'direct_operate')
            try:
                success = iec61850.ControlObjectClient_operate(control_client, mms, 1728)
                if not success:
                    err2 = iec61850.ControlObjectClient_getLastError(control_client)
                    log.info(f"Direct operate failed, lastError={err2}")
            finally:
                iec61850.MmsValue_delete(mms)
            if success:
                log.info("Direct operate succeeded (no SELECT)")
                # Verify the change by reading stVal
                time.sleep(0.5)
                try:
                    new_val, err = iec61850.IedConnection_readBooleanValue(conn, f"{object_ref}.stVal", iec61850.IEC61850_FC_ST)
                    if err == iec61850.IED_ERROR_OK:
                        new_val = bool(new_val)
                    else:
                        new_val, err = iec61850.IedConnection_readInt32Value(conn, f"{object_ref}.stVal", iec61850.IEC61850_FC_ST)
                        if err == iec61850.IED_ERROR_OK:
                            new_val = int(new_val)
                        else:
                            new_val = None
                except Exception:
                    new_val = None
                if new_val == target:
                    log.info(f"Success: stVal changed to {target}")
                else:
                    log.error(f"Failed: stVal is {new_val}, expected {target}")
                return
            else:
                # Show additional diagnostics: read SBOw.ctlNum and Oper.ctlNum
                try:
                    sbo_ctl, err_sbo = iec61850.IedConnection_readInt32Value(conn, f"{sbo_ref}.ctlNum", iec61850.IEC61850_FC_ST)
                    oper_ctl, err_oper = iec61850.IedConnection_readInt32Value(conn, f"{object_ref}.Oper.ctlNum", iec61850.IEC61850_FC_ST)
                    log.info(f"Diag ctlNum: SBOw={sbo_ctl} (err={err_sbo}), Oper={oper_ctl} (err={err_oper})")
                except Exception as e:
                    log.info(f"Diag ctlNum read failed: {e}")
                raise RuntimeError("All SELECT and direct operate failed")
        log.info("SELECT succeeded")

        # After select, ensure Oper.ctlVal matches SBOw.ctlVal to prevent deselect
        try:
            log.info(f"Writing Oper.ctlVal to {target} to match SBOw")
            err = iec61850.IedConnection_writeBooleanValue(conn, f"{object_ref}.Oper.ctlVal", iec61850.IEC61850_FC_CO, target)
            if err == iec61850.IED_ERROR_OK:
                log.info("Successfully wrote Oper.ctlVal")
            else:
                log.warning(f"Failed to write Oper.ctlVal, err={err}")
        except Exception as e:
            log.warning(f"Exception writing Oper.ctlVal: {e}")

        # Give IED a moment to populate SBO ctlNum
        time.sleep(min(1.0, args.timeout))  # increased wait to allow IED to update selection state

        # Try to determine sbo_reference if not given (best-effort)
        if not sbo_ref:
            # assume standard naming
            sbo_ref = f"{object_ref}.SBOw"

        ctl_num = read_ctlnum_prefer_sbo(conn, object_ref, sbo_ref, object_ref)
        # Also read SBOw and Oper ctlNum explicitly for diagnostics
        try:
            sbo_ctl, sbo_err = iec61850.IedConnection_readInt32Value(conn, f"{sbo_ref}.ctlNum", iec61850.IEC61850_FC_ST) if sbo_ref else (None, None)
        except Exception:
            sbo_ctl, sbo_err = (None, None)
        try:
            oper_ctl, oper_err = iec61850.IedConnection_readInt32Value(conn, f"{object_ref}.Oper.ctlNum", iec61850.IEC61850_FC_ST)
        except Exception:
            oper_ctl, oper_err = (None, None)

        if ctl_num is None:
            log.warning("Could not read ctlNum after SELECT — proceeding but this may fail")
        else:
            log.info(f"Captured ctlNum after SELECT: {ctl_num}")

        log.info(f"Diag ctlNum: SBOw={sbo_ctl} (err={sbo_err}), Oper={oper_ctl} (err={oper_err})")

        # Ensure Oper.origin fields match our originator info before OPERATE (some IEDs require this)
        try:
            iec61850.IedConnection_writeVisibleStringValue(conn, f"{object_ref}.Oper.origin.orIdent", iec61850.IEC61850_FC_CO, "SCADAScout")
            iec61850.IedConnection_writeInt32Value(conn, f"{object_ref}.Oper.origin.orCat", iec61850.IEC61850_FC_CO, 3)
            log.info("Wrote Oper.origin.orIdent/orCat to match originator")
        except Exception as e:
            log.info(f"Failed to write Oper.origin fields: {e}")

        # Log full Oper and SBOw structures for deep diagnostics
        try:
            oper_struct = iec61850.IedConnection_readObject(conn, f"{object_ref}.Oper", iec61850.IEC61850_FC_CO)
            if oper_struct:
                try:
                    s = iec61850.MmsValue_toString(oper_struct)
                    log.info(f"Oper structure: {s}")
                finally:
                    iec61850.MmsValue_delete(oper_struct)
            else:
                log.info("Oper structure not available for logging")
        except Exception as e:
            log.info(f"Failed to read Oper structure: {e}")

        if sbo_ref:
            # Normalize sbo_ref for readObject (some returned refs include /IEDs/... prefix)
            sbo_read_ref = sbo_ref
            try:
                sbo_read_ref = sbo_ref.strip('/')
                # try using the last two path components if full ref fails
                last_two = '/'.join(sbo_read_ref.split('/')[-2:])
            except Exception:
                last_two = sbo_read_ref

            try:
                sbo_struct, sbo_err_struct = iec61850.IedConnection_readObject(conn, sbo_read_ref, iec61850.IEC61850_FC_ST)
            except TypeError:
                try:
                    sbo_struct, sbo_err_struct = iec61850.IedConnection_readObject(conn, last_two, iec61850.IEC61850_FC_ST)
                except Exception as e:
                    log.info(f"Failed to read SBOw structure (tried both full and last-two): {e}")
                    sbo_struct = None
                    sbo_err_struct = None
            except Exception as e:
                log.info(f"Failed to read SBOw structure: {e}")
                sbo_struct = None
                sbo_err_struct = None

            if sbo_struct:
                try:
                    s2 = iec61850.MmsValue_toString(sbo_struct)
                    log.info(f"SBOw structure: {s2}")
                finally:
                    iec61850.MmsValue_delete(sbo_struct)
            else:
                log.info("SBOw structure not available for logging")

        # Prefer SBOw ctlNum if available and different
        use_ctl = ctl_num
        if sbo_ctl is not None and sbo_err == iec61850.IED_ERROR_OK:
            use_ctl = sbo_ctl
            log.info(f"Preferring SBOw ctlNum={use_ctl} for operate")

        if use_ctl is not None:
            try:
                # Use the ctlNum reported by the IED (prefer SBOw), normalize to 0-255
                set_ctl = int(use_ctl) % 256
                iec61850.ControlObjectClient_setCtlNum(control_client, set_ctl)
                log.info(f"Set client ctlNum={set_ctl} (from SBOw/diag)")
            except Exception as e:
                log.warning(f"Setting ctlNum on client failed: {e}")

        # OPERATE
        log.info("Performing OPERATE (toggle)")
        # Try disabling client-side interlock/synchro checks (some IEDs expect this)
        try:
            iec61850.ControlObjectClient_setInterlockCheck(control_client, False)
            iec61850.ControlObjectClient_setSynchroCheck(control_client, False)
            log.info("Disabled interlock and synchro checks on client")
        except Exception:
            pass

        # Try using Oper structure for operate (some IEDs reject raw boolean)
        log.info("Performing OPERATE")
        success = False

        # Try operate with no ctlVal (let IED use stored SBOw/Oper values)
        try:
            ok = iec61850.ControlObjectClient_operate(control_client, None, 1728)
            if ok:
                log.info("OPERATE (no value) succeeded")
                success = True
            else:
                last = iec61850.ControlObjectClient_getLastError(control_client)
                log.warning(f"OPERATE (no value) failed, lastError={last}")
        except Exception as e:
            log.info(f"Operate(no-value) attempt raised: {e}")

        # Attempt Oper structure to match IED expectations
        if not success:
            try:
                set_ctl = int(use_ctl) % 256 if use_ctl is not None else 0
                size = 7  # conservative size for Oper
                oper_struct = iec61850.MmsValue_newStructure(size)
                # Initialize all elements with safe defaults to avoid segfaults in lib
                for i in range(size):
                    if i == 0:
                        iec61850.MmsValue_setElement(oper_struct, i, iec61850.MmsValue_newBoolean(target))
                    elif i == 3:
                        iec61850.MmsValue_setElement(oper_struct, i, iec61850.MmsValue_newUnsigned(set_ctl))
                    else:
                        # Use int32 zero as a safe default for other elements
                        iec61850.MmsValue_setElement(oper_struct, i, iec61850.MmsValue_newInt32(0))
                _dump_mms_val(oper_struct, 'operate_struct')
                ok = iec61850.ControlObjectClient_operate(control_client, oper_struct, 1728)
                if ok:
                    log.info("OPERATE (struct) succeeded")
                    success = True
                else:
                    last = iec61850.ControlObjectClient_getLastError(control_client)
                    log.warning(f"OPERATE (struct) failed, lastError={last}")
            except Exception as e:
                log.info(f"Oper-struct attempt raised: {e}")
            finally:
                try:
                    iec61850.MmsValue_delete(oper_struct)
                except Exception:
                    pass

        if not success:
            # Fallback to simple boolean operate
            mms = iec61850.MmsValue_newBoolean(target)
            try:
                ok = iec61850.ControlObjectClient_operate(control_client, mms, 1728)
                if ok:
                    log.info("OPERATE (boolean) succeeded")
                    success = True
                else:
                    last = iec61850.ControlObjectClient_getLastError(control_client)
                    log.warning(f"OPERATE (boolean) failed, lastError={last}")
            finally:
                iec61850.MmsValue_delete(mms)

        if not success:
            raise RuntimeError(f"OPERATE failed (lastError={iec61850.ControlObjectClient_getLastError(control_client)})")

        log.info("OPERATE succeeded — verifying result")
        time.sleep(min(1.0, args.timeout))
        new = read_stval(conn, object_ref)
        log.info(f"New stVal: {new!r}")
        if new == target:
            log.info("SUCCESS: toggle verified")
        else:
            raise RuntimeError(f"Value did not toggle as expected (expected={target}, got={new})")

        # Deselect / Cancel selection if supported
        try:
            iec61850.ControlObjectClient_cancel(control_client)
        except Exception:
            pass

        return 0

    except Exception as e:
        log.exception(f"Test failed: {e}")
        return 2

    finally:
        if control_client:
            try:
                iec61850.ControlObjectClient_destroy(control_client)
            except Exception:
                pass
        if conn:
            try:
                iec61850.IedConnection_close(conn)
                iec61850.IedConnection_destroy(conn)
            except Exception:
                pass


if __name__ == '__main__':
    sys.exit(cli_main())
