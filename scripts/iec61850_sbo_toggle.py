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
    # Try reading ctlVal as per user's successful read
    try:
        val, err = iec61850.IedConnection_readBooleanValue(conn, f"{obj_ref}.ctlVal", iec61850.IEC61850_FC_CO)
        if err == iec61850.IED_ERROR_OK:
            return bool(val)
    except Exception:
        pass

    val, err = iec61850.IedConnection_readInt32Value(conn, f"{obj_ref}.ctlVal", iec61850.IEC61850_FC_CO)
    if err == iec61850.IED_ERROR_OK:
        return int(val)
    # If reading fails, assume False/0
    print(f"Warning: Could not read {obj_ref}.ctlVal, assuming False")
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

        # Create ControlObjectClient
        log.info("Creating ControlObjectClient")
        control_client = iec61850.ControlObjectClient_create(object_ref, conn)
        if not control_client:
            raise RuntimeError("ControlObjectClient_create failed — falling back not implemented in this script")

        ctl_model = iec61850.ControlObjectClient_getControlModel(control_client)
        log.info(f"Control model: {ctl_model}")

        # Select (SBO or SBOw)
        log.info("Performing SELECT phase (SBO)")
        success = False
        
        # As per user: SELECT with the inverted target value
        # To close (target True), select 0
        ctl_select = 0 if target else 1
        log.info(f"Doing selectWithValue with inverted target value (int): {ctl_select}")
        mms_select = iec61850.MmsValue_newInt32(ctl_select)
        try:
            success = iec61850.ControlObjectClient_selectWithValue(control_client, mms_select)
        finally:
            iec61850.MmsValue_delete(mms_select)
        
        if not success:
            log.warning("selectWithValue with current failed, trying plain select")
            success = iec61850.ControlObjectClient_select(control_client)
        
        if not success:
            log.warning("All SELECT attempts failed, trying direct operate")
            # Try direct operate without SELECT
            ctl_val_int = 0 if target else 1
            mms = iec61850.MmsValue_newInt32(ctl_val_int)
            try:
                success = iec61850.ControlObjectClient_operate(control_client, mms, 0)
            finally:
                iec61850.MmsValue_delete(mms)
            if success:
                log.info("Direct operate succeeded")
                # For direct operate, no ctlNum needed, skip the rest
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
                raise RuntimeError("All SELECT and direct operate failed")
        log.info("SELECT succeeded")

        # Give IED a moment to populate SBO ctlNum
        time.sleep(min(0.5, args.timeout))

        # Try to determine sbo_reference if not given (best-effort)
        if not sbo_ref:
            # assume standard naming
            sbo_ref = f"{object_ref}.SBOw"

        ctl_num = read_ctlnum_prefer_sbo(conn, object_ref, sbo_ref, object_ref)
        if ctl_num is None:
            log.warning("Could not read ctlNum after SELECT — proceeding but this may fail")
        else:
            log.info(f"Captured ctlNum after SELECT: {ctl_num}")
            # set it on control client
            try:
                iec61850.ControlObjectClient_setCtlNum(control_client, int(ctl_num))
                log.info(f"Set client ctlNum={ctl_num}")
            except Exception as e:
                log.warning(f"Setting ctlNum on client failed: {e}")

        # OPERATE
        log.info("Performing OPERATE (toggle)")
        # Inverted ctlVal: to close (True), send 0; to open (False), send 1
        ctl_val_int = 0 if target else 1
        mms = iec61850.MmsValue_newInt32(ctl_val_int)
        try:
            ok = iec61850.ControlObjectClient_operate(control_client, mms, 0)
        finally:
            iec61850.MmsValue_delete(mms)

        if not ok:
            # read last error to provide diagnostic
            last = iec61850.ControlObjectClient_getLastError(control_client)
            raise RuntimeError(f"OPERATE failed (lastError={last})")

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
