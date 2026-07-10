@echo off
cd /d "%~dp0"
start "" http://127.0.0.1:8801
python -m uvicorn hotscout.app:app --port 8801
