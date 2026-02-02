#!/usr/bin/env python3
"""
Quick PLC IDE GUI Test - Verify debug stepping works in the actual UI
"""
import sys
from pathlib import Path

# Must run this from project root
print("""
╔══════════════════════════════════════════════════════════════════════╗
║                   PLC IDE DEBUG TEST INSTRUCTIONS                    ║
╚══════════════════════════════════════════════════════════════════════╝

This test will open the PLC IDE. Follow these steps to verify the fixes:

1️⃣  CREATE A TEST PROGRAM
   - Click "New Program" button
   - Name it "DebugTest"
   - Replace template code with:

PROGRAM DebugTest
VAR
    counter : INT := 0;
    running : BOOL := TRUE;
END_VAR

(* Test comment handling *)
IF running THEN
    counter := counter + 1;  // Increment counter
END_IF;

(* Reset at 10 *)
IF counter >= 10 THEN
    counter := 0;
END_IF;

END_PROGRAM

2️⃣  COMPILE THE PROGRAM
   - Press F7 or click "Compile" button
   - Should compile successfully (no errors from comments)

3️⃣  TEST BREAKPOINTS
   - Click on line with "counter := counter + 1;"
   - Press F9 to set breakpoint (red dot should appear)
   - Press F9 again to verify toggle (dot disappears/reappears)

4️⃣  START DEBUG MODE
   - Click "⚙️ Task Settings"
   - Check your program in the list
   - Click OK
   - Click "🐛 DEBUG" button (or Shift+F5)
   - Should start without errors

5️⃣  TEST STEPPING
   - When breakpoint hits, execution pauses
   - Press F10 (Step Over) - should advance one line
   - Press F8 (Continue) - should continue running
   - Watch the counter increment in Variables tab
   - Press F11 (Step Into) - should also work

6️⃣  VERIFY FIXES
   ✓ Comments don't cause syntax errors
   ✓ Breakpoints properly pause execution  
   ✓ F8/F10/F11 stepping works
   ✓ Variables update correctly
   ✓ No "cannot join current thread" errors on stop

╔══════════════════════════════════════════════════════════════════════╗
║ Starting SCADA Scout with PLC IDE...                                ║
╚══════════════════════════════════════════════════════════════════════╝
""")

input("Press ENTER to start SCADA Scout... ")

# Run main
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from main import main
main()
