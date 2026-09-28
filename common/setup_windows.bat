@echo off
chcp 65001 >nul
echo === Ustanovka paketov ===
python -m pip install --upgrade pip
python -m pip install ultralytics onnx onnxruntime clearml gradio opencv-python pillow
echo.
echo === Proverka ===
python check_env.py
pause
