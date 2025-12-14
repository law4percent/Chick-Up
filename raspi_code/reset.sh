#!/bin/bash
# reset.sh - kill leftover Thonny and main.py processes

echo "Killing leftover Thonny and main.py processes..."

# Kill Thonny backend
pkill -f cp_launcher.py

# Kill previous main.py runs
pkill -f main.py

echo "Done."
