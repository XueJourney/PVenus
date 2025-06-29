@echo off
chcp 65001 >nul
echo ========= [PVenus] 开始打包 main.py =========

:: 检查 Nuitka 是否已安装
where nuitka >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未安装 Nuitka，请运行 pip install nuitka 后重试！
    pause
    exit /b
)

:: 开始打包
nuitka GUI/mainGUI.py ^
--standalone ^
--onefile ^
--windows-disable-console ^
--enable-plugin=tk-inter ^
--output-dir=build ^
--show-progress

echo.
echo ========= ✅ 打包完成！请查看 build\main.exe =========
pause
