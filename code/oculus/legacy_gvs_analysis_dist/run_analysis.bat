@echo off
echo ==========================================
echo      GVS Analysis Pipeline
echo ==========================================
echo.

echo [1/3] Checking/Installing Requirements...
pip install -r requirements.txt
echo.

echo [2/3] Running Segmentation...
python scripts/segmentation.py
echo.

echo [3/3] Running Visualization...
python scripts/visualize_interactive.py --batch-dir data
echo.

echo ==========================================
echo Done! Check the 'data' folder for results.
echo ==========================================
pause
