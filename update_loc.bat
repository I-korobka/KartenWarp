@echo off
cd /d %~dp0
python utils/update_po.py
pause