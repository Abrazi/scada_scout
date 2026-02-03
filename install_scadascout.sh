#!/bin/bash
echo "Installing SCADA Scout..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Installation complete!"
