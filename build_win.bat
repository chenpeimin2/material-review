@echo off
chcp 65001
echo ==========================================
echo      Material Review Windows 打包脚本
echo ==========================================

:: 1. 检查 Python 环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Python，请先安装 Python 3.9+ 并添加到 PATH 环境变量。
    pause
    exit /b 1
)

:: 2. 安装依赖
echo [INFO] 正在检查并安装依赖...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 3. 清理旧文件
echo [INFO] 清理旧的构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del *.spec

:: 4. 开始打包
echo [INFO] 正在打包 (PyInstaller)...
:: 注意：Windows 下 --add-data 使用分号 ; 分隔
pyinstaller --noconfirm --onedir --windowed --name "MaterialReview" ^
    --add-data "config.yaml;." ^
    --add-data "src;src" ^
    --hidden-import "PIL" ^
    --hidden-import "PIL._tkinter_finder" ^
    gui.py

if %errorlevel% neq 0 (
    echo [ERROR] 打包失败！
    pause
    exit /b 1
)

:: 5. 压缩为 Zip (调用 PowerShell)
echo [INFO] 正在创建压缩包...
powershell -Command "Compress-Archive -Path 'dist\MaterialReview' -DestinationPath 'dist\MaterialReview_Win.zip' -Force"

echo ==========================================
echo [SUCCESS] 打包完成！
echo 文件位置: dist\MaterialReview_Win.zip
echo ==========================================
pause
