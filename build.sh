#!/bin/bash
# Material Review 一键打包脚本
# 简单直接的打包方案

set -e

echo "🚀 Material Review 打包工具"
echo "=============================="
echo ""

# 1. 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ 虚拟环境已激活"
else
    echo "✗ 未找到虚拟环境，请先运行: python3 -m venv venv"
    exit 1
fi

# 2. 清理旧文件
echo "🧹 清理旧文件..."
rm -rf build dist *.spec

# 3. 使用 PyInstaller 打包 GUI 版本
echo "📦 开始打包..."
# 设置目标 macOS 版本，避免系统版本检测错误
export MACOSX_DEPLOYMENT_TARGET=11.0

pyinstaller --name="MaterialReview" \
    --windowed \
    --onedir \
    --add-data="config.yaml:." \
    --add-data="main.py:." \
    --add-data="src:src" \
    --hidden-import=PIL \
    --hidden-import=yaml \
    --hidden-import=click \
    --hidden-import=rich \
    --hidden-import=jinja2 \
    --hidden-import=zhipuai \
    --hidden-import=openai \
    --hidden-import=cv2 \
    --hidden-import=numpy \
    --hidden-import=imaplib \
    --hidden-import=email \
    --hidden-import=ssl \
    --runtime-hook=pyi_rth_cv2fix.py \
    --noconfirm \
    gui.py

echo ""
echo "✅ 打包完成！"
echo ""
echo "📁 输出位置: dist/MaterialReview.app"
echo "📏 应用大小: $(du -sh dist/MaterialReview.app | cut -f1)"
echo ""
echo "💡 测试命令:"
echo "   open dist/MaterialReview.app"
echo ""
echo "🧩 创建 DMG 安装包..."
DMG_PATH="dist/MaterialReview.dmg"
VOL_NAME="MaterialReview"
hdiutil create -volname "$VOL_NAME" -srcfolder "dist/MaterialReview.app" -ov -format UDZO "$DMG_PATH"
echo "✅ DMG 完成: $DMG_PATH"
echo "📏 DMG 大小: $(du -sh "$DMG_PATH" | cut -f1)"
echo ""
