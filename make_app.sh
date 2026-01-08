#!/bin/bash
# 创建基于 Shell 的 macOS App
# 这种方式不使用 PyInstaller，而是直接打包源码和依赖，通过 Shell 脚本启动
# 优势：兼容性好，由于不生成二进制文件，不会受 macOS 26 版本号影响

set -e

APP_NAME="MaterialReview"
DIST_DIR="dist"
APP_PATH="$DIST_DIR/$APP_NAME.app"
RESOURCES_DIR="$APP_PATH/Contents/Resources"
APP_SRC_DIR="$RESOURCES_DIR/app"
WHEELS_DIR="$RESOURCES_DIR/wheels"

echo "🚀 开始创建 Material Review (Shell版)..."

# 1. 清理和创建目录
rm -rf "$DIST_DIR"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_SRC_DIR"
mkdir -p "$WHEELS_DIR"

# 2. 下载依赖包 (离线安装用)
echo "📥 下载依赖包..."
# 临时激活 venv 确保 pip 可用
if [ -d "venv" ]; then
    source venv/bin/activate
fi
pip download -d "$WHEELS_DIR" -r requirements.txt --no-binary=:none: --only-binary=:all: --platform macosx_11_0_arm64 --platform macosx_12_0_arm64 --python-version 39 --implementation cp

# 2.1 下载独立 Python 环境 (原生 ARM64)
# 解决 Rosetta 崩溃问题和系统版本兼容问题
PYTHON_URL="https://github.com/indygreg/python-build-standalone/releases/download/20240224/cpython-3.9.18+20240224-aarch64-apple-darwin-install_only.tar.gz"
PYTHON_ARCHIVE="python_standalone.tar.gz"

echo "🐍 下载独立 Python 环境..."
curl -L -o "$PYTHON_ARCHIVE" "$PYTHON_URL"

echo "📂 解压 Python 环境..."
mkdir -p "$RESOURCES_DIR/python"
tar -xzf "$PYTHON_ARCHIVE" -C "$RESOURCES_DIR/python" --strip-components=1
rm "$PYTHON_ARCHIVE"

# 3. 复制项目文件
echo "Cc 复制源代码..."
cp -R src "$APP_SRC_DIR/"
cp gui.py "$APP_SRC_DIR/"
cp main.py "$APP_SRC_DIR/"
cp config.yaml "$APP_SRC_DIR/"
cp requirements.txt "$APP_SRC_DIR/"

# 4. 创建启动脚本
echo "📜 创建启动脚本..."
LAUNCHER="$APP_PATH/Contents/MacOS/$APP_NAME"
cat > "$LAUNCHER" << 'EOF'
#!/bin/bash
# Material Review 启动脚本

# 获取当前脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# 资源目录
RESOURCES_DIR="$DIR/../Resources"
APP_SRC_DIR="$RESOURCES_DIR/app"
WHEELS_DIR="$RESOURCES_DIR/wheels"
# 使用内置的独立 Python
PYTHON_HOME="$RESOURCES_DIR/python"
PYTHON_EXEC="$PYTHON_HOME/bin/python3"
PIP_EXEC="$PYTHON_HOME/bin/pip3"

# 设置环境变量，确保 Python 找到自己的库，避免加载系统不兼容的库
export PYTHONHOME="$PYTHON_HOME"
export PYTHONPATH="$APP_SRC_DIR"
# 强制使用内置的 Tcl/Tk
export TCL_LIBRARY="$PYTHON_HOME/lib/tcl8.6"
export TK_LIBRARY="$PYTHON_HOME/lib/tk8.6"
# 优先使用内置 Python
export PATH="$PYTHON_HOME/bin:$PATH"
# 清除可能存在的虚拟环境干扰
unset VIRTUAL_ENV

# 切换到应用源目录
cd "$APP_SRC_DIR"

# 检查依赖标记文件
INSTALLED_MARKER="$RESOURCES_DIR/.installed"

if [ ! -f "$INSTALLED_MARKER" ]; then
    # 使用 osascript 显示初始化进度对话框
    osascript -e 'display notification "正在初始化内置运行环境(原生ARM64)，请稍候..." with title "Material Review"'
    
    echo "正在安装内置依赖..."
    "$PIP_EXEC" install --no-index --find-links="$WHEELS_DIR" -r requirements.txt
    
    if [ $? -eq 0 ]; then
        touch "$INSTALLED_MARKER"
        osascript -e 'display notification "环境初始化完成，正在启动..." with title "Material Review"'
    else
        osascript -e 'display alert "环境初始化失败" message "请查看控制台日志了解详情。"'
        exit 1
    fi
fi

# 启动应用
"$PYTHON_EXEC" gui.py
EOF

chmod +x "$LAUNCHER"

# 5. 创建 Info.plist
echo "📝 创建 Info.plist..."
cat > "$APP_PATH/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.cpm.materialreview</string>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo "✅ App 创建完成: $APP_PATH"
echo "📦 大小: $(du -sh $APP_PATH | cut -f1)"
