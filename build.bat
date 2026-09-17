@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   打包 抖音直播录制软件（单文件 exe，不带版本号）
echo ============================================
echo.

rem 清理旧的带版本号产物，避免和新的混淆
if exist "dist\DouyinLiveRecorder-v0.3.exe" del /q "dist\DouyinLiveRecorder-v0.3.exe"

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean DouyinLiveRecorder.spec

echo.
echo 打包完成！产物在 dist\DouyinLiveRecorder.exe
echo.
pause
