#!/bin/bash
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi
python3 src/main.py
