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
    --add-data="src:src" \
    --hidden-import=PIL \
    --hidden-import=yaml \
    --hidden-import=click \
    --hidden-import=rich \
    --hidden-import=jinja2 \
    --hidden-import=zhipuai \
    --hidden-import=openai \
    --collect-all cv2 \
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
echo "📦 分发方法:"
echo "   1. 压缩: cd dist && zip -r MaterialReview.zip MaterialReview.app"
echo "   2. 发送 MaterialReview.zip 给同事"
echo "   3. 同事解压后拖到应用程序文件夹即可使用"
echo ""
