#!/usr/bin/env python3
"""
素材视频审核工作流 - 主入口
自动下载邮件中的视频附件，使用 AI 进行内容审核，生成审核报告。
"""

import os
import sys
import io
import time
sys.path = [p for p in sys.path if 'cv2' not in os.path.basename(p)]

from pathlib import Path
from datetime import datetime

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# 强制 stdout/stderr 使用 UTF-8 编码，解决 Windows 下 GBK 无法输出特殊字符的问题
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

console = Console()

# 配置文件路径：优先使用当前工作目录下的 config.yaml
# 这样可以通过改变工作目录来切换配置和数据存储位置（解决 App 沙盒只读问题）
CONFIG_PATH = Path.cwd() / "config.yaml"


def load_config() -> dict:
    """加载配置文件"""
    # 如果当前目录下没有 config.yaml，尝试回退到脚本所在目录查找（兼容旧模式/开发模式）
    if not CONFIG_PATH.exists():
        script_dir_config = Path(__file__).parent / "config.yaml"
        if script_dir_config.exists():
             return load_yaml_safe(script_dir_config)
             
        console.print(f"[red]✗ 配置文件不存在：{CONFIG_PATH}[/]")
        console.print("[yellow]请先复制 config.yaml.example 并填写配置[/]")
        sys.exit(1)
    
    return load_yaml_safe(CONFIG_PATH)


def load_yaml_safe(path: Path) -> dict:
    """安全加载 YAML，处理各种编码"""
    encodings = ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'cp936']
    for enc in encodings:
        try:
            with open(path, 'r', encoding=enc) as f:
                return yaml.safe_load(f) or {}
        except UnicodeDecodeError:
            continue
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8', errors='replace')
    return yaml.safe_load(text) or {}



def ensure_directories(config: dict):
    """确保目录存在"""
    paths = config.get('paths', {})
    for key in ['downloads', 'screenshots', 'reports']:
        dir_path = paths.get(key, f'./{key}')
        Path(dir_path).mkdir(parents=True, exist_ok=True)

def resolve_path(base_dir: Path, path_str: str) -> Path:
    ps = os.path.expanduser(os.path.expandvars(path_str or ''))
    if os.path.isabs(ps):
        return Path(os.path.normpath(ps))
    return (base_dir / ps).resolve()


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """素材视频审核工作流
    
    自动下载邮件中的视频附件，使用 AI 进行内容审核，生成审核报告。
    """
    pass


@cli.command()
def rules():
    """显示 AI 审核规则（当前配置）"""
    config = load_config()
    review_conf = config.get('review', {})
    import json as _json
    console.print(Panel("AI 审核规则", style="blue"))
    console.print(_json.dumps(review_conf, ensure_ascii=False, indent=2))


@cli.command()
def test_email():
    """测试邮箱连接"""
    console.print(Panel("[bold]测试邮箱连接[/]", style="blue"))
    
    config = load_config()
    email_config = config.get('email', {})
    
    from src.email_handler import EmailHandler
    handler = EmailHandler(email_config)
    if handler.connect():
        handler.disconnect()
    else:
        console.print("[yellow]请检查以下内容：[/]")
        console.print("  1. 邮箱账号是否正确")
        console.print("  2. 授权码是否正确（不是登录密码）")
        console.print("  3. 是否开启了 IMAP 服务")
        sys.exit(1)


@cli.command()
def test_ai():
    """测试 AI 连接"""
    console.print(Panel("[bold]测试 AI 连接[/]", style="blue"))
    
    config = load_config()
    ai_config = config.get('ai', {})
    review_config = config.get('review', {})
    
    # 合并配置
    full_config = {**ai_config, 'review': review_config}
    
    from src.ai_reviewer import AIReviewer
    reviewer = AIReviewer(full_config)
    
    if reviewer.test_connection():
        console.print("\n[green]✓ AI 连接测试成功！[/]")
    else:
        console.print("\n[red]✗ AI 连接测试失败[/]")
        if getattr(reviewer, 'last_error', None):
            console.print(f"[yellow]错误详情：{str(reviewer.last_error)[:200]}[/]")
        console.print("[yellow]常见原因：[/]")
        console.print("  1) API Key 无效或未配置")
        console.print("  2) 模型名不正确（建议使用: glm-4v-flash）")
        console.print("  3) 网络或地区访问受限")
        sys.exit(1)


@cli.command()
@click.option('--file', '-f', 'video_file', default=None, help='指定视频文件路径')
@click.option('--max-frames', '-n', default=200, help='最大提取帧数')
@click.option('--fps', default=None, type=float, help='抽帧频率 (FPS)，覆盖配置')
def test_video(video_file, max_frames, fps):
    """测试视频预处理功能"""
    console.print(Panel("[bold]测试视频预处理[/]", style="blue"))
    
    config = load_config()
    ensure_directories(config)
    
    paths = config.get('paths', {})
    download_path = paths.get('downloads', './downloads')
    screenshot_path = paths.get('screenshots', './screenshots')
    
    # 确定要测试的视频
    if video_file:
        if not os.path.exists(video_file):
            console.print(f"[red]✗ 视频文件不存在：{video_file}[/]")
            sys.exit(1)
        test_video_path = video_file
    else:
        # 自动选择下载目录中的第一个视频
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        videos = [f for f in Path(download_path).iterdir() if f.suffix.lower() in video_extensions]
        if not videos:
            console.print(f"[yellow]在 {download_path} 中没有找到视频文件[/]")
            console.print("[dim]提示：使用 --file 指定视频文件路径[/]")
            return
        test_video_path = str(videos[0])
        console.print(f"[dim]自动选择视频：{videos[0].name}[/]")
    
    video_config = config.get('video', {})
    from src.video_processor import VideoProcessor
    processor = VideoProcessor(video_config)
    
    # 测试1: 获取视频信息
    console.print("\n[bold cyan]测试1: 获取视频信息[/]")
    info = processor.get_video_info(test_video_path)
    if info:
        table = Table(show_header=False, box=None)
        table.add_column("属性", style="dim")
        table.add_column("值", style="green")
        table.add_row("文件名", info.filename)
        table.add_row("时长", f"{info.duration:.2f} 秒")
        table.add_row("分辨率", f"{info.width} x {info.height}")
        table.add_row("帧率", f"{info.fps:.2f} fps")
        table.add_row("总帧数", str(info.frame_count))
        table.add_row("文件大小", f"{info.file_size / 1024 / 1024:.2f} MB")
        console.print(table)
        console.print("[green]✓ 视频信息获取成功[/]")
    else:
        console.print("[red]✗ 视频信息获取失败[/]")
        sys.exit(1)
    
    # 测试2: 提取关键帧（使用 FPS）
    effective_fps = fps if fps is not None else video_config.get('extract_fps', 4)
    console.print(f"\n[bold cyan]测试2: 提取视频关键帧（每秒 {effective_fps} 帧，最多 {max_frames} 帧）[/]")
    frames = processor.extract_frames(test_video_path, fps=effective_fps, max_frames=max_frames)
    if frames:
        # 创建帧保存目录
        video_name = Path(test_video_path).stem
        frames_dir = Path(screenshot_path) / f"{video_name}_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        
        console.print(f"  共提取 [green]{len(frames)}[/] 帧")
        for i, frame in enumerate(frames):
            # 保存帧到文件
            frame_file = frames_dir / f"frame_{i+1:02d}_{frame.timestamp:.1f}s.jpg"
            frame.save(str(frame_file))
            console.print(f"  帧{i+1}: 时间=[cyan]{frame.timestamp:.2f}s[/], 尺寸={frame.width}x{frame.height}, 已保存")
        
        console.print(f"  帧已保存至: [dim]{frames_dir}[/]")
        console.print("[green]✓ 帧提取成功[/]")
    else:
        console.print("[red]✗ 帧提取失败[/]")
        sys.exit(1)
    
    # 测试3: 截图功能
    console.print("\n[bold cyan]测试3: 视频截图[/]")
    test_timestamp = min(5.0, info.duration / 2)  # 取5秒或视频中点
    screenshot_file = Path(screenshot_path) / f"test_screenshot_{Path(test_video_path).stem}.jpg"
    screenshot = processor.capture_screenshot(test_video_path, test_timestamp, str(screenshot_file))
    if screenshot:
        console.print(f"  截图时间点: [cyan]{test_timestamp:.2f}s[/]")
        console.print(f"  保存路径: [dim]{screenshot}[/]")
        console.print("[green]✓ 截图成功[/]")
    else:
        console.print("[red]✗ 截图失败[/]")
        sys.exit(1)
    
    console.print("\n[green bold]✓ 视频预处理测试全部通过！[/]")


@cli.command()
@click.option('--file', '-f', 'video_file', required=True, help='指定视频文件路径')
@click.option('--threshold', '-t', default=30.0, help='场景变化阈值（0-100），越小越敏感，默认30')
@click.option('--min-interval', '-i', default=0.1, help='最小采样间隔（秒），默认0.1')
@click.option('--max-frames', '-n', default=200, help='最大提取帧数')
def test_scene(video_file, threshold, min_interval, max_frames):
    """测试场景变化检测帧提取（智能抽帧，只在画面变化时提取）"""
    console.print(Panel("[bold]场景变化检测测试[/]", style="blue"))
    
    config = load_config()
    ensure_directories(config)
    
    paths = config.get('paths', {})
    screenshot_path = paths.get('screenshots', './screenshots')
    
    # 检查文件
    if not os.path.exists(video_file):
        console.print(f"[red]✗ 视频文件不存在：{video_file}[/]")
        sys.exit(1)
    
    video_config = config.get('video', {})
    from src.video_processor import VideoProcessor
    processor = VideoProcessor(video_config)
    
    # 获取视频信息
    info = processor.get_video_info(video_file)
    if not info:
        console.print("[red]✗ 无法获取视频信息[/]")
        sys.exit(1)
    
    console.print(f"[dim]阈值: {threshold}, 最小间隔: {min_interval}s, 最大帧数: {max_frames}[/]")
    
    # 使用场景变化检测提取帧
    frames = processor.extract_frames_scene_change(
        video_file, 
        threshold=threshold, 
        min_interval=min_interval, 
        max_frames=max_frames
    )
    
    if frames:
        # 创建帧保存目录
        video_name = Path(video_file).stem
        frames_dir = Path(screenshot_path) / f"{video_name}_scene_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        
        console.print(f"\n共提取 [green]{len(frames)}[/] 帧")
        for i, frame in enumerate(frames):
            frame_file = frames_dir / f"scene_{i+1:03d}_{frame.timestamp:.1f}s.jpg"
            frame.save(str(frame_file))
            if i < 10 or i >= len(frames) - 3:  # 只显示前10帧和后3帧
                console.print(f"  帧{i+1}: 时间=[cyan]{frame.timestamp:.2f}s[/], 已保存")
            elif i == 10:
                console.print(f"  ... 省略中间 {len(frames) - 13} 帧 ...")
        
        console.print(f"\n帧已保存至: [dim]{frames_dir}[/]")
        console.print("[green]✓ 场景变化检测完成！[/]")
    else:
        console.print("[red]✗ 帧提取失败[/]")
        sys.exit(1)


@cli.command()
@click.option('--file', '-f', 'video_file', required=True, help='指定视频文件路径')
@click.option('--fps', default=1.0, help='抽帧频率')
@click.option('--cols', default=3, help='网格列数')
def test_grid(video_file, fps, cols):
    """测试网格拼图生成（将多帧合成一张图）"""
    console.print(Panel("[bold]网格拼图测试[/]", style="blue"))
    
    config = load_config()
    ensure_directories(config)
    
    paths = config.get('paths', {})
    screenshot_path = paths.get('screenshots', './screenshots')
    
    if not os.path.exists(video_file):
        console.print(f"[red]✗ 视频文件不存在：{video_file}[/]")
        sys.exit(1)
        
    video_config = config.get('video', {})
    # 临时修改配置用于测试
    test_config = {**video_config, 'extract_fps': fps, 'grid_cols': cols}
    from src.video_processor import VideoProcessor
    processor = VideoProcessor(test_config)
    
    # 1. 提取帧
    frames = processor.extract_frames(video_file)
    if not frames:
        console.print("[red]✗ 提取帧失败[/]")
        sys.exit(1)
        
    # 2. 生成网格图
    grids = processor.create_frame_grid(frames, cols=cols)
    
    # 3. 保存网格图
    video_name = Path(video_file).stem
    grid_dir = Path(screenshot_path) / f"{video_name}_grids"
    grid_dir.mkdir(parents=True, exist_ok=True)
    
    saved_paths = processor.save_grid_images(grids, str(grid_dir), basename=video_name)
    
    console.print(f"\n[green]✓ 成功生成 {len(saved_paths)} 张网格图[/]")
    console.print(f"保存目录: [bold]{grid_dir}[/]")
    for p in saved_paths:
        console.print(f"  - {Path(p).name}")


@cli.command()
@click.argument('image_path')
@click.option('--grid', is_flag=True, help='是否为网格拼图（使用专用 Prompt）')
def test_image(image_path, grid):
    """测试单张图片的 AI 审核（用于调试审核规则）"""
    import base64
    from dataclasses import dataclass
    
    console.print(Panel("[bold]单图 AI 审核测试[/]", style="blue"))
    
    # 检查文件
    if not os.path.exists(image_path):
        console.print(f"[red]✗ 图片不存在：{image_path}[/]")
        sys.exit(1)
    
    config = load_config()
    ai_config = config.get('ai', {})
    review_config = config.get('review', {})
    
    # 读取图片
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    console.print(f"[dim]图片路径：{image_path}[/]")
    console.print(f"[dim]图片大小：{len(image_data) / 1024:.1f} KB[/]")
    
    # 构建提示词
    custom_prompt = review_config.get('custom_prompt', '')
    
    if grid:
        prompt = f"""你是一个极致严谨视频内容审核专家。

【上下文】
这是一张网格拼图。

【核心任务】
请仔细检查每一格画面，列出你看到的【所有】应用名称、图标和品牌。特别要注意角落处（如右下角）的细节，以及 App Store 搜索结果列表。

【审核标准】
{custom_prompt}

【强制工作流】
1. **转录步骤**：针对每一格，先写出看到的所有 App 和品牌名称。
2. **判定步骤**：根据转录结果对照审核标准判断。

"""
    else:
        prompt = f"""你是一个专业的视频内容审核员。

【审核标准】
{custom_prompt}

【工作流】
1. 请仔细查看画面，逐个列出你看到的所有应用名称、品牌名称、Logo和文字。
2. 根据审核标准判断是否存在违规内容、竞品品牌露出或画面质量问题。

"""

    if custom_prompt:
        prompt += f"【特殊审核要求】{custom_prompt}\n\n"
    
    prompt += """【第三步】以 JSON 格式返回审核结果：
```json
{
    "visible_content": ["列出画面中看到的所有应用名称和品牌"],
    "has_issue": true或false,
    "description": "画面描述",
    "issues": [
        {
            "timestamp": "问题出现的时间戳或网格位置（如 0:15.50）",
            "category": "问题类别",
            "description": "问题描述，说明具体看到了什么违规内容",
            "severity": "low/medium/high/critical",
            "suggestion": "修改建议"
        }
    ]
}
```
如果看到了 iScreen、Widgetsmith 等竞品应用名称，必须在 issues 中标记为 critical 级别问题。
只返回 JSON。"""
    
    # 初始化 AI
    full_config = {**ai_config, 'review': review_config}
    
    provider = ai_config.get('provider', 'zhipu')
    
    if provider == 'zhipu':
        try:
            from zhipuai import ZhipuAI
            
            zhipu_config = ai_config.get('zhipu', {})
            api_key = zhipu_config.get('api_key', '')
            model = zhipu_config.get('model', 'glm-4v-flash')
            
            client = ZhipuAI(api_key=api_key)
            console.print(f"[green]✓ 智谱 AI 初始化成功 (模型: {model})[/]")
            
            # 调用 API
            img_base64 = base64.b64encode(image_data).decode('utf-8')
            
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_base64}"
                    }
                }
            ]
            
            console.print("[blue]正在分析图片...[/]")
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                temperature=0
            )
            
            response_text = response.choices[0].message.content
            console.print("\n[bold cyan]AI 原始响应：[/]")
            console.print(response_text)
            
            # 解析 JSON
            import json
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            result = json.loads(json_str)
            # 关键词后备匹配（与主流程对齐）
            competitor_keywords = {
                'iscreen', 'widgetsmith', 'color widgets', 'color widget',
                'md clock', 'top widgets', 'topwidgets', '万能小组件',
                'locket', 'widgetable', 'temas', 'screenkit', 'themify',
                'photo widget', 'photowidget'
            }
            visible_list = result.get('all_visible_apps') if grid else result.get('visible_content')
            hit = None
            if visible_list:
                apps_norm = [str(a).lower() for a in visible_list]
                for a in apps_norm:
                    for kw in competitor_keywords:
                        if kw in a:
                            hit = kw
                            break
                    if hit:
                        break
            if hit and not result.get('has_issue'):
                result['has_issue'] = True
                result.setdefault('issues', [])
                result['issues'].append({
                    'timestamp': '单图',
                    'category': '竞品品牌露出',
                    'description': f'检测到竞品关键词：{hit}',
                    'severity': 'critical',
                    'suggestion': ''
                })
            
            console.print("\n" + "="*50)
            if result.get('has_issue'):
                console.print(Panel(
                    f"[red]✗ 发现问题！[/]\n\n" + 
                    "\n".join([f"• [{i['severity']}] {i['category']}: {i['description']}" 
                              for i in result.get('issues', [])]),
                    title="审核结果",
                    style="red"
                ))
            else:
                console.print(Panel(
                    f"[green]✓ 未发现问题[/]\n\n{result.get('description', '')}",
                    title="审核结果",
                    style="green"
                ))
                
        except Exception as e:
            console.print(f"[red]✗ 分析失败：{e}[/]")
            sys.exit(1)
    elif provider == 'qwen':
        try:
            from openai import OpenAI
            
            qwen_config = ai_config.get('qwen', {})
            api_key = qwen_config.get('api_key', '')
            base_url = qwen_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
            model = qwen_config.get('model', 'qwen-vl-plus')
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            console.print(f"[green]✓ Qwen AI 初始化成功 (模型: {model})[/]")
            
            # 调用 API
            img_base64 = base64.b64encode(image_data).decode('utf-8')
            
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_base64}"
                    }
                }
            ]
            
            console.print("[blue]正在分析图片...[/]")
            
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                temperature=0
            )
            
            response_text = response.choices[0].message.content
            console.print("\n[bold cyan]AI 原始响应：[/]")
            console.print(response_text)
            
            # 解析 JSON
            import json
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            result = json.loads(json_str)
            # 关键词后备匹配（与主流程对齐）
            competitor_keywords = {
                'iscreen', 'widgetsmith', 'color widgets', 'color widget',
                'md clock', 'top widgets', 'topwidgets', '万能小组件',
                'locket', 'widgetable', 'temas', 'screenkit', 'themify',
                'photo widget', 'photowidget'
            }
            visible_list = result.get('all_visible_apps') if grid else result.get('visible_content')
            hit = None
            if visible_list:
                apps_norm = [str(a).lower() for a in visible_list]
                for a in apps_norm:
                    for kw in competitor_keywords:
                        if kw in a:
                            hit = kw
                            break
                    if hit:
                        break
            if hit and not result.get('has_issue'):
                result['has_issue'] = True
                result.setdefault('issues', [])
                result['issues'].append({
                    'timestamp': '单图',
                    'category': '竞品品牌露出',
                    'description': f'检测到竞品关键词：{hit}',
                    'severity': 'critical',
                    'suggestion': ''
                })
            
            console.print("\n" + "="*50)
            if result.get('has_issue'):
                console.print(Panel(
                    f"[red]✗ 发现问题！[/]\n\n" + 
                    "\n".join([f"• [{i['severity']}] {i['category']}: {i['description']}" 
                              for i in result.get('issues', [])]),
                    title="审核结果",
                    style="red"
                ))
            else:
                console.print(Panel(
                    f"[green]✓ 未发现问题[/]\n\n{result.get('description', '')}",
                    title="审核结果",
                    style="green"
                ))
                
        except Exception as e:
            console.print(f"[red]✗ 分析失败：{e}[/]")
            sys.exit(1)
    else:
        console.print(f"[yellow]不支持的 AI 提供商：{provider}[/]")

@cli.command()
@click.option('--sender', '-s', default=None, help='筛选发件人')
@click.option('--since', '-d', default=None, help='起始日期 (YYYY-MM-DD)')
@click.option('--subject', '-t', default=None, help='主题关键词')
def download(sender, since, subject):
    """下载邮件中的视频附件"""
    console.print(Panel("[bold]下载邮件视频附件[/]", style="blue"))
    
    config = load_config()
    ensure_directories(config)
    
    email_config = config.get('email', {})
    paths = config.get('paths', {})
    download_path = paths.get('downloads', './downloads')
    
    # 创建邮件处理器
    from src.email_handler import EmailHandler
    handler = EmailHandler(email_config)
    
    if not handler.connect():
        sys.exit(1)
    
    try:
        # 搜索邮件
        emails = handler.search_emails(
            sender=sender,
            since_date=since,
            subject_contains=subject,
            only_with_video=True
        )
        
        if not emails:
            console.print("[yellow]没有找到符合条件的邮件[/]")
            return
        
        # 显示找到的邮件
        table = Table(title="找到的邮件")
        table.add_column("序号", style="cyan", width=6)
        table.add_column("主题", style="green")
        table.add_column("发件人", style="yellow")
        table.add_column("日期", style="blue")
        table.add_column("附件", style="magenta")
        
        for i, email_info in enumerate(emails, 1):
            attachments = ', '.join(email_info.attachments[:3])
            if len(email_info.attachments) > 3:
                attachments += f' +{len(email_info.attachments) - 3}个'
            
            table.add_row(
                str(i),
                email_info.subject[:40] + ('...' if len(email_info.subject) > 40 else ''),
                email_info.sender[:30] + ('...' if len(email_info.sender) > 30 else ''),
                email_info.date.strftime('%Y-%m-%d %H:%M'),
                attachments
            )
        
        console.print(table)
        
        # 确认下载 (GUI 模式下直接下载，不询问)
        # if not click.confirm('\n是否下载这些视频附件？', default=True):
        #     console.print("[yellow]已取消[/]")
        #     return
        console.print(f"[cyan]准备下载 {len(emails)} 封邮件的附件...[/]")
        
        # 下载所有附件
        all_downloaded = []
        for email_info in emails:
            console.print(f"\n[blue]处理邮件：{email_info.subject}[/]")
            downloaded = handler.download_attachments(
                email_info.email_id,
                download_path,
                only_video=True
            )
            all_downloaded.extend(downloaded)
        
        console.print(f"\n[green]✓ 共下载 {len(all_downloaded)} 个视频文件到 {download_path}[/]")
        
    finally:
        handler.disconnect()


@cli.command()
@click.option('--file', '-f', 'video_file', default=None, help='指定视频文件路径')
@click.option('--download-first', '-d', is_flag=True, help='先下载邮件附件再审核')
@click.option('--sender', '-s', default=None, help='筛选发件人（与 -d 配合使用）')
@click.option('--since', default=None, help='起始日期（与 -d 配合使用）')
def review(video_file, download_first, sender, since):
    """审核视频内容"""
    console.print(Panel("[bold]AI 视频内容审核[/]", style="blue"))
    
    config = load_config()
    ensure_directories(config)
    
    paths = config.get('paths', {})
    download_path = paths.get('downloads', './downloads')
    screenshot_path = paths.get('screenshots', './screenshots')
    report_path = paths.get('reports', './reports')
    
    videos_to_review = []
    email_info_map = {}  # video_path -> email_info
    
    # 如果指定了视频文件
    if video_file:
        if not os.path.exists(video_file):
            console.print(f"[red]✗ 视频文件不存在：{video_file}[/]")
            sys.exit(1)
        videos_to_review.append(video_file)
    
    # 如果需要先下载
    elif download_first:
        email_config = config.get('email', {})
        from src.email_handler import EmailHandler
        handler = EmailHandler(email_config)
        
        if not handler.connect():
            sys.exit(1)
        
        try:
            emails = handler.search_emails(
                sender=sender,
                since_date=since,
                only_with_video=True
            )
            
            if not emails:
                console.print("[yellow]没有找到包含视频附件的邮件[/]")
                return
            
            for email_info in emails:
                console.print(f"\n[blue]下载邮件附件：{email_info.subject}[/]")
                downloaded = handler.download_attachments(
                    email_info.email_id,
                    download_path,
                    only_video=True
                )
                
                for att in downloaded:
                    videos_to_review.append(att.filepath)
                    email_info_map[att.filepath] = {
                        'sender': email_info.sender,
                        'subject': email_info.subject,
                        'date': email_info.date
                    }
        finally:
            handler.disconnect()
    
    # 否则扫描下载目录
    else:
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        for file in Path(download_path).iterdir():
            if file.suffix.lower() in video_extensions:
                videos_to_review.append(str(file))
        
        if not videos_to_review:
            console.print(f"[yellow]在 {download_path} 中没有找到视频文件[/]")
            console.print("[dim]提示：使用 --file 指定视频，或使用 --download-first 先下载邮件附件[/]")
            return
    
    console.print(f"\n[blue]待审核视频数量：{len(videos_to_review)}[/]")
    
    # 初始化各模块
    video_config = config.get('video', {})
    ai_config = config.get('ai', {})
    review_config = config.get('review', {})
    report_config = config.get('report', {})
    
    from src.video_processor import VideoProcessor
    from src.ai_reviewer import AIReviewer
    from src.report_generator import ReportGenerator
    processor = VideoProcessor(video_config)
    reviewer = AIReviewer({**ai_config, 'review': review_config})
    generator = ReportGenerator(report_config)
    
    total_start_time = time.time()
    
    # 逐个审核视频
    for video_path in videos_to_review:
        video_start_time = time.time()
        console.print(f"\n{'='*60}")
        console.print(f"[bold blue]审核视频：{Path(video_path).name}[/]")
        console.print('='*60)
        
        # 获取视频信息
        video_info = processor.get_video_info(video_path)
        if not video_info:
            console.print(f"[red]✗ 无法读取视频信息，跳过[/]")
            continue
        
        # 提取帧
        frames = processor.extract_frames(video_path)
        if not frames:
            console.print(f"[red]✗ 无法提取视频帧，跳过[/]")
            continue
        
        # AI 审核（逐帧模式）
        result = reviewer.review_video(frames, video_path)
        if not result:
            console.print(f"[red]✗ AI 审核出现严重错误，停止后续审核[/]")
            break
        
        # 为问题生成截图
        screenshots = {}
        if result.issues:
            console.print(f"[blue]正在生成问题截图...[/]")
            video_name = Path(video_path).stem
            video_screenshot_dir = Path(screenshot_path) / video_name
            video_screenshot_dir.mkdir(parents=True, exist_ok=True)
            for issue in result.issues:
                nearest_path = processor.save_frame_nearest(
                    frames, issue.timestamp, str(video_screenshot_dir), video_name
                )
                if not nearest_path:
                    continue
                screenshots[issue.timestamp] = nearest_path
            console.print(f"[blue]正在为问题截图添加标注...[/]")
            for issue in result.issues:
                src_path = screenshots.get(issue.timestamp)
                if not src_path:
                    continue
                label = f"{issue.category}: {issue.description}".strip()
                marked_path = processor.annotate_image_file(src_path, label)
                if marked_path:
                    screenshots[issue.timestamp] = marked_path
        
        # 生成报告
        video_name = Path(video_path).stem
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = Path(report_path) / f"{video_name}_审核报告_{timestamp}.html"
        
        email_info = email_info_map.get(video_path)
        
        generator.generate_report(
            result,
            video_info=video_info,
            email_info=email_info,
            screenshots=screenshots,
            output_path=str(report_file)
        )
        
        video_elapsed = time.time() - video_start_time
        
        # 显示结果摘要
        console.print()
        if result.is_compliant:
            console.print(Panel(
                f"[green]✓ 审核通过[/]\n评分：{int(result.overall_score)}/100\n处理时长：{video_elapsed:.1f} 秒",
                title="结果",
                style="green"
            ))
        else:
            issue_summary = f"发现 {len(result.issues)} 个问题"
            console.print(Panel(
                f"[red]✗ 审核未通过[/]\n评分：{int(result.overall_score)}/100\n{issue_summary}\n处理时长：{video_elapsed:.1f} 秒",
                title="结果",
                style="red"
            ))
    
    total_elapsed = time.time() - total_start_time
    minutes = int(total_elapsed // 60)
    seconds = total_elapsed % 60
    
    if len(videos_to_review) > 1:
        console.print(f"\n[bold green]总处理耗时：{minutes}分{seconds:.1f}秒[/]")
    
    console.print(f"\n[green]✓ 审核完成！报告保存在 {report_path}[/]")


@cli.command()
def list_videos():
    """列出下载目录中的视频文件"""
    config = load_config()
    paths = config.get('paths', {})
    download_path = paths.get('downloads', './downloads')
    
    console.print(Panel(f"[bold]下载目录中的视频文件[/]\n{download_path}", style="blue"))
    
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
    
    download_dir = Path(download_path)
    if not download_dir.exists():
        console.print("[yellow]下载目录不存在[/]")
        return
    
    videos = list(download_dir.glob('*'))
    videos = [v for v in videos if v.suffix.lower() in video_extensions]
    
    if not videos:
        console.print("[yellow]没有找到视频文件[/]")
        return
    
    table = Table()
    table.add_column("序号", style="cyan", width=6)
    table.add_column("文件名", style="green")
    table.add_column("大小", style="yellow", justify="right")
    table.add_column("修改时间", style="blue")
    
    for i, video in enumerate(sorted(videos), 1):
        size = video.stat().st_size
        size_str = format_size(size)
        mtime = datetime.fromtimestamp(video.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        
        table.add_row(str(i), video.name, size_str, mtime)
    
    console.print(table)
    console.print(f"\n共 {len(videos)} 个视频文件")


@cli.command()
def list_reports():
    """列出已生成的审核报告"""
    config = load_config()
    paths = config.get('paths', {})
    report_path = paths.get('reports', './reports')
    
    console.print(Panel(f"[bold]审核报告列表[/]\n{report_path}", style="blue"))
    
    report_dir = Path(report_path)
    if not report_dir.exists():
        console.print("[yellow]报告目录不存在[/]")
        return
    
    reports = list(report_dir.glob('*.html')) + list(report_dir.glob('*.md'))
    
    if not reports:
        console.print("[yellow]没有找到审核报告[/]")
        return
    
    table = Table()
    table.add_column("序号", style="cyan", width=6)
    table.add_column("报告名称", style="green")
    table.add_column("格式", style="magenta", width=8)
    table.add_column("生成时间", style="blue")
    
    for i, report in enumerate(sorted(reports, key=lambda x: x.stat().st_mtime, reverse=True), 1):
        mtime = datetime.fromtimestamp(report.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        fmt = report.suffix.upper()[1:]
        
        table.add_row(str(i), report.name, fmt, mtime)
    
    console.print(table)
    console.print(f"\n共 {len(reports)} 份报告")


def format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@cli.command()
@click.option('--include-downloads', is_flag=True, help='同时删除下载的视频文件')
def clean(include_downloads):
    """清理缓存文件（报告、截图等）"""
    import shutil
    
    console.print(Panel("[bold]清理缓存文件[/]", style="blue"))
    
    config = load_config()
    paths = config.get('paths', {})
    
    dirs_to_clean = {
        'screenshots': paths.get('screenshots', './screenshots'),
        'reports': paths.get('reports', './reports')
    }
    
    if include_downloads:
        dirs_to_clean['downloads'] = paths.get('downloads', './downloads')
        
    cleaned_count = 0
    cleaned_size = 0
    
    for name, path_str in dirs_to_clean.items():
        path = Path(path_str)
        if not path.exists():
            continue
            
        console.print(f"正在清理 {name} ({path})...")
        
        for item in path.iterdir():
            try:
                if item.is_file():
                    size = item.stat().st_size
                    item.unlink()
                    cleaned_count += 1
                    cleaned_size += size
                elif item.is_dir():
                    # 计算目录大小
                    for f in item.rglob('*'):
                        if f.is_file():
                            cleaned_size += f.stat().st_size
                    shutil.rmtree(item)
                    cleaned_count += 1
            except Exception as e:
                console.print(f"[red]删除 {item} 失败: {e}[/]")
                
    size_mb = cleaned_size / (1024 * 1024)
    console.print(f"\n[green]✓ 清理完成[/]")
    console.print(f"共删除 {cleaned_count} 个项目，释放空间 {size_mb:.2f} MB")

if __name__ == '__main__':
    cli()
