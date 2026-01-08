# Material Review - macOS 打包说明

## 快速开始

### 一键打包
```bash
chmod +x build_mac.sh
./build_mac.sh
```

打包完成后，会在 `dist` 目录生成：
- `MaterialReview.app` - macOS 应用程序
- `MaterialReview.dmg` - DMG 安装镜像（推荐分发）

## 详细步骤

### 1. 环境准备

确保你的 Mac 上已安装：
- Python 3.8 或更高版本
- pip（Python 包管理器）

检查 Python 版本：
```bash
python3 --version
```

### 2. 安装依赖

脚本会自动创建虚拟环境并安装依赖，但你也可以手动安装：

```bash
# 创建虚拟环境（可选）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置应用

在打包前，请确保 `config.yaml` 已正确配置：
- 邮箱账号和授权码
- AI API Key
- 审核规则

**重要**：配置文件会被打包进应用，如需修改需要重新打包。

### 4. 执行打包

```bash
./build_mac.sh
```

打包过程包括：
1. ✓ 检查 Python 环境
2. ✓ 创建/激活虚拟环境
3. ✓ 安装项目依赖
4. ✓ 清理旧的构建文件
5. ✓ 使用 PyInstaller 打包
6. ✓ 创建 DMG 安装包

### 5. 测试应用

打包完成后，测试应用是否正常运行：

```bash
# 方式1：直接运行可执行文件
dist/MaterialReview.app/Contents/MacOS/material-review --help

# 方式2：测试各项功能
dist/MaterialReview.app/Contents/MacOS/material-review test-email
dist/MaterialReview.app/Contents/MacOS/material-review test-ai
```

## 分发给同事

### 方式1：分发 DMG（推荐）

1. 将 `dist/MaterialReview.dmg` 发送给同事
2. 同事双击打开 DMG
3. 拖拽 `MaterialReview.app` 到应用程序文件夹
4. 完成！

### 方式2：分发 .app

1. 压缩 `dist/MaterialReview.app`：
   ```bash
   cd dist
   zip -r MaterialReview.zip MaterialReview.app
   ```
2. 将 `MaterialReview.zip` 发送给同事
3. 同事解压后拖拽到应用程序文件夹

## 使用说明（给同事）

### 安装

1. 将 `MaterialReview.app` 拖拽到应用程序文件夹
2. 首次运行时，如果系统提示"无法打开"，请：
   - 打开"系统偏好设置" → "安全性与隐私"
   - 点击"仍要打开"按钮
   
   或者在终端执行：
   ```bash
   xattr -cr /Applications/MaterialReview.app
   ```

### 使用

打开终端（Terminal），运行：

```bash
# 查看帮助
/Applications/MaterialReview.app/Contents/MacOS/material-review --help

# 测试邮箱连接
/Applications/MaterialReview.app/Contents/MacOS/material-review test-email

# 测试 AI 连接
/Applications/MaterialReview.app/Contents/MacOS/material-review test-ai

# 下载邮件附件
/Applications/MaterialReview.app/Contents/MacOS/material-review download

# 审核视频
/Applications/MaterialReview.app/Contents/MacOS/material-review review

# 列出视频文件
/Applications/MaterialReview.app/Contents/MacOS/material-review list-videos

# 列出审核报告
/Applications/MaterialReview.app/Contents/MacOS/material-review list-reports
```

### 创建命令别名（可选）

为了方便使用，可以创建命令别名：

```bash
# 编辑 shell 配置文件
nano ~/.zshrc  # 或 ~/.bash_profile

# 添加以下行
alias material-review='/Applications/MaterialReview.app/Contents/MacOS/material-review'

# 保存后重新加载
source ~/.zshrc
```

之后就可以直接使用：
```bash
material-review --help
material-review review
```

## 常见问题

### Q1: 打包失败，提示找不到模块

**解决方案**：
1. 确保所有依赖都在 `requirements.txt` 中
2. 检查 `material_review.spec` 中的 `hiddenimports` 列表
3. 手动添加缺失的模块到 `hiddenimports`

### Q2: 应用无法打开，提示"已损坏"

**解决方案**：
```bash
# 移除隔离属性
xattr -cr /Applications/MaterialReview.app

# 或者在系统设置中允许运行
# 系统偏好设置 → 安全性与隐私 → 仍要打开
```

### Q3: 配置文件在哪里？

配置文件被打包在应用内部：
```
MaterialReview.app/Contents/MacOS/config.yaml
```

如需修改配置，需要：
1. 修改项目根目录的 `config.yaml`
2. 重新运行 `./build_mac.sh` 打包

### Q4: 如何减小应用体积？

1. 在 `material_review.spec` 中排除不需要的模块
2. 使用 `upx` 压缩（已启用）
3. 移除不必要的依赖

### Q5: 如何添加应用图标？

1. 准备 `.icns` 格式的图标文件
2. 在 `material_review.spec` 中修改：
   ```python
   app = BUNDLE(
       ...
       icon='path/to/icon.icns',
       ...
   )
   ```
3. 重新打包

## 高级配置

### 自定义应用信息

编辑 `material_review.spec` 中的 `info_plist`：

```python
info_plist={
    'CFBundleShortVersionString': '1.0.0',  # 版本号
    'CFBundleName': 'MaterialReview',        # 应用名称
    'CFBundleDisplayName': 'Material Review', # 显示名称
    'NSHumanReadableCopyright': 'Copyright © 2026',  # 版权信息
}
```

### 代码签名（可选）

如果需要分发到 App Store 或需要公证：

```bash
# 签名应用
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/MaterialReview.app

# 公证应用
xcrun notarytool submit dist/MaterialReview.dmg --apple-id your@email.com --password app-specific-password --team-id TEAMID
```

## 项目结构

```
material-review/
├── main.py                    # 主入口
├── config.yaml                # 配置文件
├── requirements.txt           # Python 依赖
├── material_review.spec       # PyInstaller 配置
├── build_mac.sh              # 打包脚本
├── src/                      # 源代码
│   ├── email_handler.py
│   ├── video_processor.py
│   ├── ai_reviewer.py
│   └── report_generator.py
├── dist/                     # 打包输出（自动生成）
│   ├── MaterialReview.app
│   └── MaterialReview.dmg
└── build/                    # 构建临时文件（自动生成）
```

## 更新日志

### v1.0.0 (2026-01-07)
- ✓ 初始版本
- ✓ 支持邮件下载
- ✓ 支持视频审核
- ✓ 支持 AI 分析
- ✓ 生成审核报告

## 技术支持

如有问题，请联系开发团队。
