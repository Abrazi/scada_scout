"""
Test PLC IDE with verbose logging to verify variable updates.

Run this test, then:
1. Open PLC IDE (Ctrl+Shift+P)
2. Create a new program
3. Paste this code:

PROGRAM TestCounter
VAR
    counter : INT := 0;
    enabled : BOOL := TRUE;
END_VAR

IF enabled THEN
    counter := counter + 1;
END_IF

END_PROGRAM

4. Compile (F7)
5. Create a task and assign the program
6. Enable "📋 Verbose Logging" checkbox
7. Start PLC (F5)
8. Watch the output console - you should see:
   - [SCAN X] messages every 10 scans
   - [TASK] messages showing task execution
   - [PROG] messages showing program execution
   - [VARS] messages showing variable changes
9. Check Variables panel - counter should increment
"""
print(__doc__)
