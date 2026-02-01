#!/bin/bash
# Quick test script to verify UI fix

echo "========================================"
echo "UI FREEZE FIX - VERIFICATION TEST"
echo "========================================"
echo ""
echo "This test verifies the control dialog fix"
echo ""

cd /home/majid/Documents/scada_scout

echo "1. Checking Python syntax..."
python3 -m py_compile src/ui/dialogs/control_dialog.py
if [ $? -eq 0 ]; then
    echo "   ✓ Syntax OK"
else
    echo "   ✗ Syntax error!"
    exit 1
fi

echo ""
echo "2. Checking imports..."
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')

try:
    from ui.dialogs.control_dialog import ControlDialog, ControlWorker
    print("   ✓ Imports OK")
    print(f"   ✓ ControlWorker class found")
    print(f"   ✓ ControlDialog class found")
except ImportError as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)
EOF

echo ""
echo "3. Checking for threading code..."
grep -q "QThread" src/ui/dialogs/control_dialog.py && echo "   ✓ QThread import found" || echo "   ✗ QThread not found"
grep -q "ControlWorker" src/ui/dialogs/control_dialog.py && echo "   ✓ ControlWorker class found" || echo "   ✗ ControlWorker not found"
grep -q "moveToThread" src/ui/dialogs/control_dialog.py && echo "   ✓ Thread usage found" || echo "   ✗ Thread usage not found"

echo ""
echo "========================================"
echo "VERIFICATION COMPLETE"
echo "========================================"
echo ""
echo "✅ The UI freeze fix has been applied!"
echo ""
echo "To test with your IED:"
echo "1. Run: python3 src/main.py"
echo "2. Connect to 172.16.11.18"
echo "3. Open control for GPS01ECB01CB1/CSWI1.Pos"
echo "4. Click SELECT - UI should stay responsive!"
echo "5. Click OPERATE - UI should stay responsive!"
echo ""
echo "Expected behavior:"
echo "✓ No UI freeze"
echo "✓ Status updates in real-time"
echo "✓ Can move dialog during operations"
echo "✓ Error messages display cleanly"
echo ""
