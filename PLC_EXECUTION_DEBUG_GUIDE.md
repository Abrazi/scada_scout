# PLC IDE - Execution Visibility & Debug Guide

## ✅ FIXED: Variable Updates & Verbose Logging

### New Features Added

#### 1. **📋 Verbose Logging Toggle**
- Located in Debug Controls toolbar
- **Enable it to see detailed execution trace** including:
  - `[SCAN X]` - Every 10th scan with task/program counts
  - `[TASK]` - Task execution start
  - `[PROG]` - Program execution or skip reasons
  - `[VARS]` - Variable changes (shows var=value when changed)

#### 2. **Debug Stepping Now Works**
- **F11** (⤵ Step Into) - Step into next statement
- **F10** (⤋ Step Over) - Step over current statement  
- **F8** (▶▶ Continue) - Continue from breakpoint
- **F9** (🔴 Breakpoint) - Toggle breakpoint at cursor

---

## 🔍 How to Verify PLC is Running

### Step 1: Create a Test Program

1. Open PLC IDE (Ctrl+Shift+P)
2. Click "New Program" in project tree
3. Name it: `TestCounter`
4. Paste this code:

```st
PROGRAM TestCounter
VAR
    counter : INT := 0;
    enabled : BOOL := TRUE;
    increment : INT := 1;
END_VAR

IF enabled THEN
    counter := counter + increment;
END_IF

END_PROGRAM
```

5. **Compile (F7)** - Should show "✓ Compilation successful"

### Step 2: Create a Task

1. Click "New Task" button
2. Set Task Name: `MainTask`
3. Set Interval: `100` ms (10 times per second)
4. Set Priority: `1`
5. **Assign Program**: Check `TestCounter` in the program list
6. Click OK

### Step 3: Enable Verbose Logging

1. In Debug Controls toolbar, **check "📋 Verbose Logging"**
2. Output console should show: "✓ Verbose logging ENABLED - detailed execution trace will appear below"

### Step 4: Start PLC

1. Click **▶ RUN (F5)** button
2. Mode indicator should turn **GREEN** showing "RUN"
3. **Watch the Output Console** - you should see every ~1 second:
   ```
   [SCAN 10] Executing 1 tasks, 1 programs total
     [TASK] MainTask: Starting with 1 programs
       [PROG] TestCounter: Executing...
       [VARS] counter=10, enabled=True, increment=1
   [SCAN 20] Executing 1 tasks, 1 programs total
     [TASK] MainTask: Starting with 1 programs
       [PROG] TestCounter: Executing...
       [VARS] counter=20
   ```

### Step 5: Verify Variables Update

1. Look at **Variables panel** (left side)
2. You should see:
   ```
   Name       Type    Value   Quality
   counter    INT     123     good
   enabled    BOOL    True    good
   increment  INT     1       good
   ```
3. Counter should **increment continuously** (refreshes every 500ms)

---

## 🐛 Debug Mode Testing

### Step 1: Set Breakpoint

1. In editor, click line with `counter := counter + increment;`
2. Press **F9** or click **🔴 Breakpoint (F9)** button
3. Red circle should appear in gutter

### Step 2: Start Debug Mode

1. Click **🐛 DEBUG** button
2. Mode indicator turns **BLUE** showing "DEBUG"
3. Execution will pause at breakpoint (yellow highlight)

### Step 3: Use Stepping

1. **F11 (Step Into)**: Execute one line, update call stack
2. Check **Call Stack panel** - should show:
   ```
   TestCounter:1
   ```
3. Check **Variables panel** - values update after each step
4. **F10 (Step Over)**: Same as step into for simple statements
5. **F8 (Continue)**: Resume until next breakpoint

### Step 4: Watch Expressions

1. In Watch List panel, click "Add..."
2. Enter: `counter * 2`
3. Click Add
4. Watch should show `counter * 2 = 246` (updates as counter changes)

---

## ⚠️ Troubleshooting

### Problem: "No values shown in Variables panel"

**Possible Causes:**

1. **Program not compiled**
   - Solution: Press F7, check for "✓ Compilation successful"

2. **Program not assigned to task**
   - Solution: Click ⚙️ Task Settings, assign program to task

3. **PLC not running**
   - Solution: Check mode indicator is GREEN (RUN) or BLUE (DEBUG)

4. **Task disabled**
   - Solution: In task list, ensure task has checkbox enabled

### Problem: "Output console shows nothing during RUN"

**Solution:**
1. **Enable Verbose Logging** (check 📋 Verbose Logging checkbox)
2. If still nothing appears, check:
   - Mode indicator is GREEN (RUN) or BLUE (DEBUG)
   - At least one task is enabled and has programs assigned
   - Scan time is updating (shows "Scan: X.Xms" in toolbar)

### Problem: "Debug stepping doesn't work"

**Possible Causes:**

1. **Not in DEBUG mode**
   - Solution: Click 🐛 DEBUG button (not ▶ RUN)

2. **No breakpoint set**
   - Solution: Press F9 on executable line (not VAR or END_PROGRAM)

3. **Breakpoint on wrong line**
   - Solution: Set breakpoint on executable statement like `counter := counter + 1;`

### Problem: "Variables update but values are wrong"

**Check:**
1. Initial values in VAR block
2. Logic in IF/THEN statements
3. Data types match (INT for integers, BOOL for true/false)

---

## 📊 What the Logs Mean

### Scan Logs
```
[SCAN 10] Executing 1 tasks, 1 programs total
```
- Shows scan number (every 10th scan)
- Number of enabled cyclic tasks
- Total programs in PLC

### Task Logs
```
  [TASK] MainTask: Starting with 1 programs
```
- Task name
- Number of programs assigned to task

### Program Logs
```
    [PROG] TestCounter: Executing...
```
- Program name
- "Executing..." = running normally
- "SKIPPED (disabled)" = program disabled
- "SKIPPED (not compiled)" = needs compilation

### Variable Logs
```
      [VARS] counter=123, enabled=True
```
- Only shows variables that **changed value** since last scan
- Format: `variable_name=new_value`

---

## 🎯 Expected Performance

With a 100ms task interval:
- **Scan time**: 0.1-0.5ms (very fast)
- **Counter increment**: +10 per second (100ms * 10 = 1 second)
- **Variable refresh**: Every 500ms in UI
- **Verbose log**: Every ~1 second (10 scans)

If scan time > 10ms, you may have:
- Too many programs in one task
- Complex calculations in program
- Breakpoint paused execution

---

## 🔧 Advanced: Execution Flow

1. **Start PLC (F5 or 🐛)**
   - Calls `runtime.start()` or `runtime.start_debug()`
   - Initializes variable contexts with initial values
   - Starts scan thread (loops at ~10ms minimum)

2. **Each Scan**
   - Sort tasks by priority
   - For each enabled cyclic task:
     - Execute each assigned program
     - Decode bytecode
     - Execute Python code
     - **Save context** (critical for persistence!)
     - Update variable.current_value
     - Update watches (in DEBUG mode)

3. **UI Update (500ms timer)**
   - Read `program.local_variables.get_variable(name)`
   - Display in Variables panel
   - Update watch expressions
   - Update call stack (DEBUG mode)

---

## ✅ Success Checklist

- [ ] Can compile program without errors (F7)
- [ ] Can create task and assign program
- [ ] Can enable verbose logging (📋 checkbox)
- [ ] See scan/task/program logs in output
- [ ] See variable changes in logs
- [ ] Variables panel shows live values
- [ ] Counter increments continuously
- [ ] Can set breakpoint (F9)
- [ ] Can start DEBUG mode (🐛)
- [ ] Can step through code (F10/F11)
- [ ] Call stack updates during debug
- [ ] Watch expressions evaluate correctly

---

## 📝 Example Output (Verbose Logging Enabled)

```
✓ Compilation successful
PLC started (RUN mode)
✓ Verbose logging ENABLED - detailed execution trace will appear below

[SCAN 10] Executing 1 tasks, 1 programs total
  [TASK] MainTask: Starting with 1 programs
    [PROG] TestCounter: Executing...
      [VARS] counter=10

[SCAN 20] Executing 1 tasks, 1 programs total
  [TASK] MainTask: Starting with 1 programs
    [PROG] TestCounter: Executing...
      [VARS] counter=20

[SCAN 30] Executing 1 tasks, 1 programs total
  [TASK] MainTask: Starting with 1 programs
    [PROG] TestCounter: Executing...
      [VARS] counter=30
```

Each group appears approximately every second (10 scans * 100ms interval).

---

## 🚀 Quick Test Command

Run this to verify everything works:

```bash
cd /home/majid/Documents/scada_scout
python3 src/main.py
```

Then follow "How to Verify PLC is Running" steps above.
