# SCADA Scout — Scripting User Guide

A practical, copy‑pasteable tutorial for writing Python scripts inside SCADA Scout. Includes
- complete API reference for the in‑app scripting context (`ctx`) ✅
- tokenized tag usage and examples (portable scripts) 🏷️
- IEC 61850 control recipes (SBO-aware) ⚡
- runnable snippets you can paste into the Script Editor or run programmatically

---

## Quick start (30 seconds) ⚡
1. Open SCADA Scout → Tools → **Python Scripts** (or open the Script Editor in the UI).
2. Paste any example from this guide into the editor.
3. Click **Run Once** to test, or **Start Continuous** and choose an interval (s).
4. View output in the **Event Log**.

Tip: press Ctrl+Space in the editor to insert `{{TAG:...}}` tokens for tags.

---

## Which script style should I use?
- `tick(ctx)` — runner calls repeatedly at the configured interval (recommended for polling/monitoring).
- `loop(ctx)` or `main(ctx)` — called once; your function must manage looping and check `ctx.should_stop()`.
- Raw top‑level script — executed as‑is (can block if long running).

Example templates (copy/paste):

```python
# tick style (recommended)
def tick(ctx):
    v = ctx.get('Simulator::holding:40010', 0)
    ctx.log('info', f'value={v}')

# loop style (runs once; must check ctx.should_stop())
def loop(ctx):
    while not ctx.should_stop():
        ctx.log('info', 'working...')
        ctx.sleep(0.5)

# one-shot / top-level
ctx.log('info', 'Running one-shot')
x = ctx.read('Simulator::holding:40010')
ctx.set('Simulator::holding:40011', x+1)
```

---

## ScriptContext (`ctx`) — API reference (with examples) 🔧
All examples are safe to copy into the editor. Replace tag addresses with values from your system (use Ctrl+Space).

- `ctx.get(tag_address, default=None)`
  - Return last-known value (non-blocking).
  - Example: `temp = ctx.get('IED1::MMXU1.Tmp.stVal', 0.0)`

- `ctx.read(tag_address)`
  - Force a best-effort read; may return last-known value if read is async.
  - Example: `val = ctx.read('ModbusDevice::holding:40010')`

- `ctx.set(tag_address, value) -> bool`
  - Write value. For IEC 61850 DOs the runtime will try to resolve the control leaf and perform safe control.
  - Example (Modbus): `ctx.set('Simulator::holding:40010', 123)`
  - Example (IEC 61850 DO — auto-resolve): `ctx.set('IED1::LLN0$XCBR$Pos', True)`

- `ctx.send_command(tag_address, value, params: dict = None) -> bool`
  - Explicit IEC 61850 control (SBO-aware). Supported params: `sbo_timeout` (ms), `originator_id`, `originator_cat`, `force_direct`, `force_sbo`, `ctl_num`, `ctl_attr`.
  - Example:

```python
params = {'sbo_timeout': 200, 'originator_id': 'SCADA_AUTO'}
ctx.send_command('IED1::LD/CSWI1.Pos', True, params=params)
```

- `ctx.list_tags(device_name=None)` — list available unique addresses
  - Example: `tags = ctx.list_tags('Simulator')`

- `ctx.sleep(seconds)` — cooperative sleep inside scripts
  - Example: `ctx.sleep(0.2)`

- `ctx.log(level, message)` — write to Event Log (`'info'|'warning'|'error'`)
  - Example: `ctx.log('warning', 'Voltage high')`

- `ctx.should_stop() -> bool` — poll inside long-running loops to stop cleanly
  - Example:

```python
while not ctx.should_stop():
    # do work
    ctx.sleep(0.1)
```

Implementation notes: see `src/core/script_runtime.py` for runtime behavior and edge-cases.

---

## Tokenized tags (recommended) 🏷️
Use `{{TAG:Device::Address[#n]}}` in scripts so they remain portable across device renames.
The editor and runtime resolve tokens automatically via `ScriptTagManager`.

Examples:
```python
# token usage (editor will resolve before run)
src = '{{TAG:Simulator::holding:40010}}'
val = ctx.get(src, 0)

# recommended: keep tokens in your saved scripts so they survive renames
```

Helpful token APIs (editor/runtime): `extract_tokens`, `get_candidates`, `resolve_code`, `update_tokens`, `set_choice`.
Files: `src/core/script_tag_manager.py`, editor helpers `src/ui/dialogs/python_script_dialog.py`.

---

## IEC 61850 control — practical recipes ⚡
- You may pass a DO or a DA; the runtime resolves the proper control DA (e.g., `Oper.ctlVal`, `ctlVal`, `SBOw`).
- `ctx.send_command()` handles SBO/select+operate automatically when appropriate; use `params` to override behavior.

Example — close breaker with retry and custom SBO timeout:

```python
def close_breaker_with_retry(ctx):
    ctrl = '{{TAG:IED1::LD/CSWI1.Pos}}'
    params = {'sbo_timeout': 300}
    for attempt in range(3):
        if ctx.send_command(ctrl, True, params=params):
            ctx.log('info', 'Breaker closed')
            return True
        ctx.log('warning', f'attempt {attempt+1} failed')
        ctx.sleep(0.5)
    ctx.log('error', 'All attempts failed')
    return False
```

See full working examples: `examples/iec61850_sbo_control_examples.py`.

---

## Best practices & safety ⚠️
- Prefer `tick(ctx)` + `ctx.sleep()` for periodic tasks (non-blocking). 
- Always check `ctx.should_stop()` in long loops. 
- Wrap IO/control in try/except and log errors via `ctx.log('error', ...)`.
- Use tokenized addresses (`{{TAG:...}}`) for portability.
- Scripts run inside the application—avoid running untrusted code.

Safe loop template (copyable):

```python
def loop(ctx):
    try:
        while not ctx.should_stop():
            try:
                v = ctx.read('{{TAG:Sensor::Temp.stVal}}')
                if v is None:
                    ctx.log('warning', 'read returned None')
                # process v...
            except Exception as exc:
                ctx.log('error', f'inner error: {exc}')
            ctx.sleep(0.5)
    finally:
        ctx.log('info', 'cleaning up')
```

---

## Troubleshooting & tips 🛠️
- Tag not found: use the editor's Ctrl+Space and token chooser; or use `tag_mgr.get_candidates()` from code.
- Ambiguous token: resolve in the editor (UI prompts) or call `ScriptTagManager` helpers.
- Control fails: increase `sbo_timeout`, enable Event Log debug, read ctlModel from the IED.
- `ctx.read()` may be asynchronous — expect last-known value on some transports.

Quick checks:
- Use **Run Once** for quick verification before starting continuous.
- Check `user_scripts.json` and `token_choices.json` for saved scripts and persisted token choices.

---

## Cheat‑sheet (quick reference)

| API / Keyword | Purpose | One-line example |
|---|---:|---|
| `tick(ctx)` | periodic entry | `def tick(ctx): ...` |
| `loop(ctx)` / `main(ctx)` | single-call managed loop | `def loop(ctx): ...` |
| `ctx.get(...)` | last-known value | `ctx.get('IED::addr', 0)` |
| `ctx.read(...)` | force read | `ctx.read('IED::addr')` |
| `ctx.set(...)` | write / control (auto-resolve) | `ctx.set('Dev::addr', 1)` |
| `ctx.send_command(...)` | IEC61850 control (SBO-aware) | `ctx.send_command('IED::CSWI.Pos', True)` |
| `ctx.sleep(s)` | cooperative sleep | `ctx.sleep(0.2)` |
| `ctx.log(lvl,msg)` | event log | `ctx.log('info','ok')` |
| `ctx.should_stop()` | graceful stop check | `while not ctx.should_stop(): ...` |
| `{{TAG:...}}` | tokenized tag | use in saved scripts |

---

## Ready-to-use copy/paste examples (runnable)

1) Monitor + action (tick)

```python
# Paste into Script Editor -> Start Continuous
def tick(ctx):
    value = ctx.get('{{TAG:Simulator::holding:40010}}', 0)
    if value > 100:
        ctx.set('{{TAG:Simulator::holding:40011}}', 0)
        ctx.log('warning', f'reset because value={value}')
```

2) One-shot IEC61850 control (Run Once)

```python
def main(ctx):
    ctrl = '{{TAG:IED1::LD/CSWI1.Pos}}'
    ctx.log('info', 'sending CLOSE')
    if ctx.send_command(ctrl, True):
        ctx.log('info', 'closed')
```

3) Programmatic test (run from plugin / interpreter)

```python
from src.core.script_runtime import run_script_once
code = "def main(ctx):\n    ctx.log('info','hello from run_script_once')\n    print(ctx.list_tags()[:5])"
run_script_once(code, device_manager_core)
```

---

## Files & examples to inspect
- Runtime: `src/core/script_runtime.py`
- Token manager: `src/core/script_tag_manager.py`
- UI editor: `src/ui/dialogs/python_script_dialog.py`
- Examples: `examples/iec61850_sbo_control_examples.py`
- Tests: `tests/test_script_runtime.py`, `tests/script_runtime_smoketest.py`
- Saved scripts: `user_scripts.json`, persisted token choices: `token_choices.json`

---

## How to validate your script locally ✅
1. Use **Run Once** in the UI to check for immediate errors.
2. If you need to run from code, call `run_script_once(code, device_manager_core)`.
3. For continuous scripts, start from the editor and then verify the script appears in `device_manager.list_user_scripts()`.
4. Run unit-tests that reference the runtime: `pytest tests/test_script_runtime.py -q`.

---

## License & safety
Scripts run with the application's privileges. Do not run untrusted code. This guide and all examples are licensed under the project license (see `LICENSE`).

---

If you'd like, I can:
- add inline links to the exact source lines referenced, or
- create a short example script that runs during `tox`/CI as a documentation smoke-test.

Happy to add those — tell me which you'd prefer and I'll update the doc. ✨
