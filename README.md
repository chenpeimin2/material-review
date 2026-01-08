# 素材视频审核工作流

自动下载邮箱中的视频附件，使用 AI 进行内容审核，生成包含问题截图的审核报告。

## 功能特性

- ✅ 自动连接网易邮箱下载视频附件
- ✅ 支持筛选发件人、日期、主题
- ✅ 使用 AI（Gemini/OpenAI）进行视频内容审核
- ✅ 自定义审核规则（内容合规、品牌相关、视频质量）
- ✅ 自动截取问题时间点的截图
- ✅ 生成美观的 HTML 审核报告

## 快速开始

### 1. 安装依赖

```bash
# 建议使用虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 安装 FFmpeg（视频处理需要）

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# 下载 https://ffmpeg.org/download.html 并添加到 PATH
```

### 3. 配置

编辑 `config.yaml` 文件：

1. **邮箱配置**
   - 填写网易邮箱账号
   - 填写授权码（不是登录密码！）
   - 获取授权码步骤：登录网页版邮箱 → 设置 → POP3/SMTP/IMAP → 开启 IMAP → 获取授权码

2. **AI 配置**
   - 选择 AI 提供商：`gemini` 或 `openai`
   - 填写对应的 API Key

3. **审核规则**
   - 可自定义开启/关闭各审核类别
   - 可添加自定义审核提示

### 4. 测试连接

```bash
# 测试邮箱连接
python main.py test-email

# 测试 AI 连接
python main.py test-ai
```

## 使用方法

### 下载邮件附件

```bash
# 下载所有包含视频的邮件附件
python3 main.py download

# 筛选发件人
python main.py download --sender "blogger@example.com"

# 筛选日期
python main.py download --since "2024-01-01"

# 筛选主题
python main.py download --subject "素材"
```

### 审核视频

```bash
# 审核下载目录中的所有视频
python main.py review

# 审核指定视频文件
python main.py review --file /path/to/video.mp4

# 先下载再审核
python main.py review --download-first

# 先下载（筛选条件）再审核
python main.py review --download-first --sender "blogger@example.com"
```

### 其他命令

```bash
# 列出下载目录中的视频
python main.py list-videos

# 列出已生成的审核报告
python main.py list-reports

# 查看帮助
python main.py --help
python main.py review --help
```

## 目录结构

```
素材审核/
├── config.yaml          # 配置文件
├── requirements.txt     # 依赖包
├── main.py              # 主入口
├── README.md            # 说明文档
├── src/
│   ├── __init__.py
│   ├── email_handler.py     # 邮件处理
│   ├── video_processor.py   # 视频处理
│   ├── ai_reviewer.py       # AI 审核
│   └── report_generator.py  # 报告生成
├── downloads/           # 下载的视频（自动创建）
├── screenshots/         # 问题截图（自动创建）
└── reports/             # 审核报告（自动创建）
```

## 审核报告示例

审核报告为 HTML 格式，包含：

- 视频基本信息
- 审核结论（通过/未通过）
- 综合评分（0-100）
- 问题列表（含截图、时间点、严重程度）
- 修改建议

## 自定义审核规则

在 `config.yaml` 中可以自定义审核规则：

```yaml
review:
  categories:
    # 关闭不需要的审核类别
    brand_relevance:
      enabled: false
    
  # 添加自定义审核要求
  custom_prompt: |
    额外要求：
    1. 检查是否有公司 logo 水印
    2. 检查背景音乐是否合适
    3. ...
```

## 常见问题

### Q: 授权码在哪里获取？
A: 登录网易邮箱网页版 → 设置 → POP3/SMTP/IMAP → 开启 IMAP 服务 → 获取授权码

### Q: 支持哪些视频格式？
A: MP4, MOV, AVI, MKV, WMV, FLV, WebM, M4V

### Q: AI 审核准确吗？
A: AI 审核有一定的准确性，但建议作为辅助工具，重要内容仍需人工复核。

### Q: 如何迁移到服务器？
1. 复制整个项目目录到服务器
2. 安装依赖：`pip install -r requirements.txt`
3. 安装 FFmpeg
4. 修改 `config.yaml` 中的路径和凭据
5. 使用 cron 设置定时任务（可选）

## License

MIT License
