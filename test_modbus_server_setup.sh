#!/bin/bash
# Quick test script for Modbus Server setup
# Tests CSV import and shows configuration summary

cd "$(dirname "$0")"

echo "=============================================="
echo "SCADA Scout - Modbus Server Setup Test"
echo "=============================================="
echo ""

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated"
else
    echo "✗ Virtual environment not found"
    echo "  Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if Gen_Registers.csv exists
if [ ! -f "Gen_Registers.csv" ]; then
    echo "✗ Gen_Registers.csv not found in project root"
    echo "  Please ensure the CSV file is present"
    exit 1
fi

echo "✓ Gen_Registers.csv found"
echo ""

# Test CSV import
echo "Testing CSV Import..."
echo "----------------------------------------------"
python test_csv_import.py Gen_Registers.csv

if [ $? -eq 0 ]; then
    echo ""
    echo "=============================================="
    echo "✓ CSV Import Test PASSED"
    echo "=============================================="
    echo ""
    echo "Next Steps:"
    echo "1. Start SCADA Scout: python src/main.py"
    echo "2. Open Scripts window"
    echo "3. Run 'Setup Generators (G1-G22)'"
    echo "4. Run 'Setup Switchgear (GPS1-GPS4)'"
    echo "5. Connect servers from Device Manager"
    echo ""
    echo "See MODBUS_SERVER_COMPLETE.md for full guide"
else
    echo ""
    echo "=============================================="
    echo "✗ CSV Import Test FAILED"
    echo "=============================================="
    echo ""
    echo "Please check:"
    echo "- CSV file format is correct"
    echo "- CSV file is UTF-8 encoded"
    echo "- Required columns are present"
    echo ""
    echo "See MODBUS_SERVER_CSV_IMPORT_GUIDE.md for format"
    exit 1
fi
