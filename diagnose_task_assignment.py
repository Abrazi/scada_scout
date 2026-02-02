#!/usr/bin/env python3
"""
PLC Task Assignment Diagnostic Tool

This script helps identify why programs aren't executing.
"""

print("""
╔══════════════════════════════════════════════════════════════╗
║  PLC TASK ASSIGNMENT DIAGNOSTIC                              ║
╚══════════════════════════════════════════════════════════════╝

PROBLEM: Your log shows:
  [TASK] test1: Starting with 0 programs

This means your task exists but has NO programs assigned!

╔══════════════════════════════════════════════════════════════╗
║  WHY THIS HAPPENS:                                           ║
╚══════════════════════════════════════════════════════════════╝

When you create a program, it's added to plc_ext.programs[]
When you create a task, it has an EMPTY program_ids[] list

The task and program exist separately - you must LINK them!

╔══════════════════════════════════════════════════════════════╗
║  HOW TO FIX:                                                 ║
╚══════════════════════════════════════════════════════════════╝

METHOD 1: Via Task Configuration Dialog
────────────────────────────────────────
1. Open PLC IDE (Ctrl+Shift+P)
2. Click ⚙️ "Task Settings" button (left panel)
3. You'll see: "Assigned Programs:" with checkboxes
4. ✓ CHECK your program name (e.g., "Counter", "TestProgram")
5. Click OK
6. Start PLC again (F5)

Now you should see:
  [TASK] test1: Starting with 1 programs
  [PROG] YourProgram: Executing...

METHOD 2: Via New Task Button
─────────────────────────────
1. Click "New Task" button
2. Enter task details (Name, Interval, Priority)
3. In "Select Programs" section, CHECK your programs
4. Click Create
5. Start PLC (F5)

METHOD 3: Manual Fix (Python Console)
─────────────────────────────────────
If you're in Python console or script:

    # Get the task and program
    task = plc_ext.tasks[0]  # Your task
    program = plc_ext.programs[0]  # Your program
    
    # Assign program to task
    if program.program_id not in task.program_ids:
        task.program_ids.append(program.program_id)
    
    # Now start runtime
    runtime.start()

╔══════════════════════════════════════════════════════════════╗
║  VERIFICATION:                                               ║
╚══════════════════════════════════════════════════════════════╝

After fixing, with VERBOSE LOGGING enabled, you should see:

✅ CORRECT OUTPUT:
  [SCAN 10] Executing 1 tasks, 1 programs total (1 assigned to tasks)
  [TASK] test1: Starting with 1 programs
    [PROG] YourProgram: Executing...
      [VARS] counter=10

❌ WRONG OUTPUT (what you had):
  [SCAN 10] Executing 1 tasks, 1 programs total (0 assigned to tasks)
  [TASK] test1: ⚠️ NO PROGRAMS ASSIGNED! (program_ids is empty)

╔══════════════════════════════════════════════════════════════╗
║  NEW FEATURES TO HELP:                                       ║
╚══════════════════════════════════════════════════════════════╝

1. ⚠️ Warning Dialog
   When you try to start PLC with empty tasks, you'll now see:
   "No tasks have programs assigned!"
   With option to open Task Settings directly

2. 📋 Improved Verbose Logging
   Shows: "(X assigned to tasks)" to indicate the problem

3. 🔔 Task Config Warning
   Yellow banner in dialog warns about empty program lists

╔══════════════════════════════════════════════════════════════╗
║  QUICK TEST:                                                 ║
╚══════════════════════════════════════════════════════════════╝

1. python3 src/main.py
2. Ctrl+Shift+P (Open PLC IDE)
3. Create program with this code:

   PROGRAM Test
   VAR
       count : INT := 0;
   END_VAR
   
   count := count + 1;
   
   END_PROGRAM

4. Compile (F7)
5. Click ⚙️ Task Settings
6. ✓ CHECK "Test" in program list
7. Click OK
8. ✓ Enable "📋 Verbose Logging"
9. Start (F5)
10. Watch logs - should see program executing!

═══════════════════════════════════════════════════════════════
Press Enter to continue...
""")
input()
