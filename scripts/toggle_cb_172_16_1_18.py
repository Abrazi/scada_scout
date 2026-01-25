"""One-shot IEC 61850 circuit-breaker toggle for IED at 172.16.11.18:102

- Designed to be runnable from SCADA Scout's Scripts UI (provides `main(ctx)`).
- Configurable at the top (HOST / PORT / OBJECT_REF). Change `OBJECT_REF` to match
  the controlled data-object on your IED if needed.

WARNING: this will operate real equipment when run. Verify `OBJECT_REF` and
authorize the action before running against production devices.
"""

from __future__ import annotations

from typing import Optional

# Use the project's IEC61850 wrapper
from src.protocols.iec61850 import iec61850_wrapper as iec61850

# --- CONFIGURATION ---
HOST = "172.16.11.18"
PORT = 102
# Object reference on the IED (relative to the IED). Replace with the correct path.
# Examples: "LD0/LLN0$XCBR$Pos"  or "LD1/LLN0$XCBR1$Pos"  or "LD1/CSWI1.Pos"
OBJECT_REF = "LD0/LLN0$XCBR$Pos"
# If True the script will send SELECT/OPERATE. Set to False to dry-run only.
DOIT = True
# Waits (seconds)
SBO_WAIT = 0.15
OPERATE_VERIFY_WAIT = 0.7


def _connect(host: str, port: int):
    conn = iec61850.IedConnection_create()
    err = iec61850.IedConnection_connect(conn, host, port)
    if err != 0:
        raise RuntimeError(f"Could not connect to {host}:{port} (error {err})")
    return conn


def _read_stval(conn, obj_ref: str) -> Optional[object]:
    """Robust stVal reader — try several likely attribute paths before giving up.

    We do not change protocol logic; this is purely a caller-side convenience to handle
    different vendor object layouts (e.g. some IEDs expose `.Oper.stVal` or `.Pos.stVal`).
    """
    candidates = [
        f"{obj_ref}.stVal",
        f"{obj_ref}.Oper.stVal",
        f"{obj_ref}.Pos.stVal",
        f"{obj_ref}.SBOw.stVal",
    ]
    for cand in candidates:
        try:
            val, err = iec61850.IedConnection_readBooleanValue(conn, cand, iec61850.IEC61850_FC_ST)
            if err == iec61850.IED_ERROR_OK:
                return bool(val)
        except Exception:
            pass
        try:
            val, err = iec61850.IedConnection_readInt32Value(conn, cand, iec61850.IEC61850_FC_ST)
            if err == iec61850.IED_ERROR_OK:
                return int(val)
        except Exception:
            pass
    return None


def _read_ctlval(conn, obj_ref: str) -> Optional[object]:
    try:
        val, err = iec61850.IedConnection_readBooleanValue(conn, f"{obj_ref}.ctlVal", iec61850.IEC61850_FC_CO)
        if err == iec61850.IED_ERROR_OK:
            return bool(val)
    except Exception:
        pass
    try:
        val, err = iec61850.IedConnection_readInt32Value(conn, f"{obj_ref}.ctlVal", iec61850.IEC61850_FC_CO)
        if err == iec61850.IED_ERROR_OK:
            return int(val)
    except Exception:
        pass
    return None


def main(ctx) -> bool:
    """One-shot script entrypoint for SCADA Scout.

    Connects directly to the IED at HOST:PORT and toggles OBJECT_REF.
    Logs progress via `ctx.log(level, msg)` so the UI event-log shows details.
    Returns True on success, False on failure.
    """
    ctx.log('warning', f"Starting IEC61850 toggle script against {HOST}:{PORT} -> {OBJECT_REF} (DOIT={DOIT})")

    conn = None
    client = None
    try:
        conn = _connect(HOST, PORT)
        ctx.log('info', 'TCP connection established')

        cur = _read_stval(conn, OBJECT_REF)
        ctx.log('info', f'Current stVal: {cur!r}')

        ctlval = _read_ctlval(conn, OBJECT_REF)
        if ctlval is not None:
            ctx.log('info', f'Current ctlVal: {ctlval!r}')

        # If we couldn't read stVal/ctlVal from the raw object, try to help the user by
        # probing common alternative addresses on the device (if accessible via DeviceManager).
        if cur is None and ctlval is None:
            try:
                # If the script is running inside SCADA Scout, the ScriptContext exposes the
                # DeviceManagerCore as ctx._dm. Use it to search for likely control tags.
                dm = getattr(ctx, '_dm', None)
                if dm:
                    alts = [u for u in dm.list_unique_addresses() if OBJECT_REF.split('/')[-1] in u or 'CSWI' in u or 'XCBR' in u]
                    if alts:
                        ctx.log('warning', 'stVal/ctlVal not readable at the requested path — found candidate tags on device:')
                        for a in alts[:10]:
                            ctx.log('info', f'  - {a}')
                        ctx.log('info', 'Tip: open the Scripts editor, press Ctrl+Space to pick one of the above tags and re-run the script.')
                        return False
            except Exception:
                pass

        # Decide target (toggle)
        if isinstance(cur, bool):
            target = not cur
        elif isinstance(cur, int):
            target = 0 if cur else 1
        else:
            # If we cannot read stVal, try ctlVal
            if isinstance(ctlval, bool):
                target = not ctlval
            elif isinstance(ctlval, int):
                target = 0 if ctlval else 1
            else:
                ctx.log('error', 'Could not determine current breaker state (stVal/ctlVal unavailable)')
                ctx.log('info', 'Actions: 1) Verify OBJECT_REF, 2) Run "Add IED + Variables (172.16.11.18)" script to populate tags, or 3) run discovery for the device from Device Tree.')
                return False

        ctx.log('info', f'Computed toggle target -> {target!r}')

        if not DOIT:
            ctx.log('warning', 'DOIT is False: dry-run only, no SELECT/OPERATE will be sent')
            return True

        # Create a ControlObjectClient and run SBO+OPERATE
        ctx.log('info', 'Creating ControlObjectClient')
        client = iec61850.ControlObjectClient_create(OBJECT_REF, conn)
        if not client:
            ctx.log('error', 'Failed to create ControlObjectClient')
            return False

        # Prefer selectWithValue where available (some IEDs expect inverted ctlVal semantics)
        ctx.log('info', 'Performing SELECT (SBO)')
        # Many IEDs expect the inverted ctlVal as the SELECT value when the ctlVal
        # encoding uses 0 = ON/close and 1 = OFF/open (legacy Siemens behaviour).
        # To be interoperable we try selectWithValue using integer 0/1 derived from target.
        ctl_select = 0 if target else 1
        mms = iec61850.MmsValue_newInt32(ctl_select)
        try:
            ok = iec61850.ControlObjectClient_selectWithValue(client, mms)
        finally:
            iec61850.MmsValue_delete(mms)

        if not ok:
            ctx.log('warning', 'selectWithValue failed, trying plain select()')
            ok = iec61850.ControlObjectClient_select(client)

        if not ok:
            ctx.log('warning', 'SELECT failed; attempting direct OPERATE as a fallback')
            # Attempt direct operate (may succeed on ctlModel that allow it)
            mms2 = iec61850.MmsValue_newInt32(0 if target else 1)
            try:
                ok = iec61850.ControlObjectClient_operate(client, mms2, 0)
            finally:
                iec61850.MmsValue_delete(mms2)
            if ok:
                ctx.log('info', 'Direct OPERATE succeeded (fallback)')
                ctx.sleep(OPERATE_VERIFY_WAIT)
                new = _read_stval(conn, OBJECT_REF)
                ctx.log('info', f'Verified stVal after direct OPERATE: {new!r}')
                return new == target
            ctx.log('error', 'All SELECT attempts failed')
            return False

        ctx.log('info', 'SELECT succeeded — waiting briefly for ctlNum (SBO)')
        ctx.sleep(SBO_WAIT)

        # Try to capture ctlNum (SBOw preferred)
        ctl_num = None
        try:
            # common SBOw naming: OBJECT_REF + '.SBOw'
            sbo_ref = f"{OBJECT_REF}.SBOw"
            val, err = iec61850.IedConnection_readInt32Value(conn, f"{sbo_ref}.ctlNum", iec61850.IEC61850_FC_ST)
            if err == iec61850.IED_ERROR_OK:
                ctl_num = int(val) % 256
        except Exception:
            ctl_num = None

        if ctl_num is None:
            try:
                val, err = iec61850.IedConnection_readInt32Value(conn, f"{OBJECT_REF}.ctlNum", iec61850.IEC61850_FC_ST)
                if err == iec61850.IED_ERROR_OK:
                    ctl_num = int(val) % 256
            except Exception:
                ctl_num = None

        if ctl_num is not None:
            try:
                iec61850.ControlObjectClient_setCtlNum(client, int(ctl_num))
                ctx.log('info', f'Set client ctlNum={ctl_num}')
            except Exception as e:
                ctx.log('warning', f'Failed to set ctlNum on client: {e}')
        else:
            ctx.log('warning', 'Could not read ctlNum after SELECT (continuing without explicit ctlNum)')

        # OPERATE (send inverted ctlVal encoding as int)
        ctx.log('info', 'Performing OPERATE (toggle)')
        mms3 = iec61850.MmsValue_newInt32(0 if target else 1)
        try:
            ok = iec61850.ControlObjectClient_operate(client, mms3, 0)
        finally:
            iec61850.MmsValue_delete(mms3)

        if not ok:
            last = iec61850.ControlObjectClient_getLastError(client)
            ctx.log('error', f'OPERATE failed (lastError={last})')
            return False

        ctx.log('info', 'OPERATE succeeded — verifying stVal')
        ctx.sleep(OPERATE_VERIFY_WAIT)
        new = _read_stval(conn, OBJECT_REF)
        ctx.log('info', f'New stVal: {new!r}')
        success = new == target

        if success:
            ctx.log('info', 'Toggle verified — SUCCESS')
        else:
            ctx.log('error', f'Toggle verification failed (expected={target}, got={new})')

        # Best-effort Cancel cleanup
        try:
            iec61850.ControlObjectClient_cancel(client)
        except Exception:
            pass

        return success

    except Exception as e:
        ctx.log('error', f'Exception during toggle: {e}')
        return False

    finally:
        try:
            if client:
                iec61850.ControlObjectClient_destroy(client)
        except Exception:
            pass
        try:
            if conn:
                iec61850.IedConnection_close(conn)
                iec61850.IedConnection_destroy(conn)
        except Exception:
            pass
