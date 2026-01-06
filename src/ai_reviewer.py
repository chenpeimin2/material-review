"""
AI 审核模块
负责调用 AI API 分析视频帧，判断内容是否合规
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


class Severity(Enum):
    """问题严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Issue:
    """审核发现的问题"""
    timestamp: float  # 问题出现的时间点（秒）
    category: str  # 问题类别
    description: str  # 问题描述
    severity: str  # 严重程度: low/medium/high/critical
    suggestion: str = ""  # 修改建议


@dataclass
class FrameAnalysis:
    """单帧分析结果"""
    timestamp: float
    is_compliant: bool
    issues: List[Issue] = field(default_factory=list)
    description: str = ""


@dataclass
class ReviewResult:
    """完整视频审核结果"""
    video_path: str
    video_filename: str
    is_compliant: bool  # 是否整体合规
    overall_score: float  # 综合评分 (0-100)
    total_frames_analyzed: int  # 分析的帧数
    issues: List[Issue] = field(default_factory=list)  # 所有问题
    summary: str = ""  # 审核总结
    frame_analyses: List[FrameAnalysis] = field(default_factory=list)  # 各帧分析
    
    def get_issues_by_severity(self, severity: str) -> List[Issue]:
        """按严重程度获取问题"""
        return [i for i in self.issues if i.severity == severity]
    
    def get_issue_timestamps(self) -> List[float]:
        """获取所有问题的时间点"""
        return list(set(i.timestamp for i in self.issues))


class AIReviewer:
    """AI 审核器"""
    
    def __init__(self, config: dict):
        """
        初始化 AI 审核器
        
        Args:
            config: AI 配置字典
        """
        self.config = config
        self.provider = config.get('provider', 'zhipu')
        self.review_config = config.get('review', {})
        
        # 初始化 AI 客户端
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """初始化 AI 客户端"""
        if self.provider == 'zhipu':
            self._init_zhipu()
        elif self.provider == 'qwen':
            self._init_qwen()
        else:
            console.print(f"[red]✗ 不支持的 AI 提供商：{self.provider}[/]")

    def _init_qwen(self):
        """初始化阿里 Qwen 客户端（使用 OpenAI 兼容接口）"""
        try:
            from openai import OpenAI
            
            qwen_config = self.config.get('qwen', {})
            api_key = qwen_config.get('api_key', '')
            base_url = qwen_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
            model_name = qwen_config.get('model', 'qwen-vl-plus')
            
            if not api_key or api_key == 'your_qwen_api_key':
                console.print("[red]✗ 请在 config.yaml 中配置 Qwen (DashScope) API Key[/]")
                return
            
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.model = model_name
            console.print(f"[green]✓ Qwen AI 初始化成功 (模型: {model_name})[/]")
            
        except ImportError:
            console.print("[red]✗ 请安装 OpenAI SDK: pip install openai[/]")
        except Exception as e:
            console.print(f"[red]✗ Qwen 初始化失败：{e}[/]")
    
    def _init_zhipu(self):
        """初始化智谱 AI 客户端"""
        try:
            from zhipuai import ZhipuAI
            
            zhipu_config = self.config.get('zhipu', {})
            api_key = zhipu_config.get('api_key', '')
            
            if not api_key or api_key == 'your_zhipu_api_key':
                console.print("[red]✗ 请在 config.yaml 中配置智谱 API Key[/]")
                return
            
            self.client = ZhipuAI(api_key=api_key)
            self.model = zhipu_config.get('model', 'glm-4v-flash')
            self.provider_type = 'zhipu'
            
            console.print(f"[green]✓ 智谱 AI 初始化成功 (模型: {self.model})[/]")
            
        except ImportError:
            console.print("[red]✗ 请安装 zhipuai: pip install zhipuai[/]")
        except Exception as e:
            console.print(f"[red]✗ 智谱 AI 初始化失败：{e}[/]")
    
    def _build_review_prompt(self) -> str:
        """构建审核提示词"""
        categories = self.review_config.get('categories', {})
        custom_prompt = self.review_config.get('custom_prompt', '')
        
        prompt = """你是一个专业的视频内容审核员。请仔细分析提供的视频帧，检查是否存在以下问题：

## 审核标准

"""
        
        # 内容合规性
        content_compliance = categories.get('content_compliance', {})
        if content_compliance.get('enabled', True):
            prompt += "### 1. 内容合规性\n"
            for item in content_compliance.get('check_items', []):
                prompt += f"- {item}\n"
            prompt += "\n"
        
        # 品牌相关性
        brand_relevance = categories.get('brand_relevance', {})
        if brand_relevance.get('enabled', True):
            prompt += "### 2. 品牌相关性\n"
            for item in brand_relevance.get('check_items', []):
                prompt += f"- {item}\n"
            prompt += "\n"
        
        # 视频质量
        video_quality = categories.get('video_quality', {})
        if video_quality.get('enabled', True):
            prompt += "### 3. 视频质量\n"
            for item in video_quality.get('check_items', []):
                prompt += f"- {item}\n"
            prompt += "\n"
        
        # 自定义提示
        if custom_prompt:
            prompt += f"### 4. 其他要求\n{custom_prompt}\n\n"
        
        prompt += """## 输出格式

请以 JSON 格式返回审核结果，格式如下：

```json
{
    "is_compliant": true/false,
    "overall_score": 0-100,
    "summary": "整体审核总结",
    "issues": [
        {
            "frame_index": 0,
            "category": "问题类别（内容合规性/品牌相关性/视频质量）",
            "description": "具体问题描述",
            "severity": "low/medium/high/critical",
            "suggestion": "修改建议"
        }
    ]
}
```

注意：
1. 如果没有发现问题，issues 返回空数组
2. overall_score 基于问题的数量和严重程度评分
3. frame_index 表示问题出现在第几帧（从0开始）
4. severity 严重程度：low（轻微）、medium（中等）、high（严重）、critical（极其严重，必须修改）

请只返回 JSON，不要有其他文字。
"""
        
        return prompt
    
    def _analyze_frames_with_zhipu(self, frames, frame_timestamps: List[float]) -> Optional[Dict]:
        """使用智谱 AI 分析帧（逐帧分析模式，因为 GLM-4V-Flash 只支持单图）"""
        import base64
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        
        all_issues = []
        frame_descriptions = []
        
        # 构建单帧分析提示词
        single_frame_prompt = f"""你是一个极致严谨的视频审核员。

【核心规则】
{self.review_config.get('custom_prompt', '')}

【审核指令】
1. 文字/App转录：列出画面中【真实存在】且【肉眼可见】的所有 App 名称及它们的大致位置（如：左上、中间、右下）。严禁凭空想象！
2. 判定违规：根据【核心规则】判断：
   - 如果是 Mico 或允许的大众软件 -> has_issue: false。
   - 如果是黑名单竞品（Widgetsmith, iScreen等） -> has_issue: true, category: "竞品品牌露出", severity: "critical"。
   - 如果是非精品内容（Roblox, Hole.io等） -> has_issue: true, category: "画面质量问题", severity: "medium"。

请严格按以下 JSON 格式回复（不要有任何开场白或结尾）：
```json
{{
    "visible_content": ["App名称(位置)", "App名称(位置)"],
    "has_issue": false,
    "description": "客观描述看到的具体内容",
    "issues": [
        {{
            "category": "问题类别",
            "description": "详细说明在什么位置看到了什么，为什么违规",
            "severity": "critical/medium"
        }}
    ]
}}
```"""

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("AI 分析帧中...", total=len(frames))
                
                # 使用二分采样算法重排帧顺序：先分析中间位置，再分析四分点，逐步细化
                # 这样可以更快地覆盖视频的不同时间段
                frame_indices = self._get_binary_sample_order(len(frames))
                
                api_error_count = 0
                max_api_errors = 3  # 连续3次API错误则退出
                
                for idx in frame_indices:
                    frame = frames[idx]
                    timestamp = frame_timestamps[idx]
                    minutes = int(timestamp // 60)
                    seconds = timestamp % 60
                    
                    # 准备单帧请求
                    img_base64 = base64.b64encode(frame.image_data).decode('utf-8')
                    
                    content = [
                        {"type": "text", "text": f"这是视频第 {minutes}分{seconds:.1f}秒 的画面。\n\n{single_frame_prompt}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                    
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=[{"role": "user", "content": content}]
                        )
                        
                        api_error_count = 0  # 成功则重置错误计数
                        response_text = response.choices[0].message.content
                        
                        # 提取 JSON
                        if "```json" in response_text:
                            json_str = response_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in response_text:
                            json_str = response_text.split("```")[1].split("```")[0].strip()
                        else:
                            json_str = response_text.strip()
                        
                        frame_result = json.loads(json_str)
                        
                        # 收集描述
                        frame_descriptions.append(f"[{minutes}:{seconds:.0f}] {frame_result.get('description', '')}")
                        
                        # 收集问题
                        if frame_result.get('has_issue') and frame_result.get('issues'):
                            violating_apps = [i.get('description', '') for i in frame_result['issues']]
                            console.print(f"[yellow]‼ 在 {minutes}:{seconds:.0f}s 命中违规内容: {violating_apps}[/]")
                            
                            for issue in frame_result['issues']:
                                all_issues.append({
                                    'frame_index': idx,
                                    'category': issue.get('category', '未分类'),
                                    'description': issue.get('description', ''),
                                    'severity': issue.get('severity', 'low'),
                                    'suggestion': issue.get('suggestion', '')
                                })
                            
                            # 优化: 发现一个问题就停止继续审核（响应用户要求）
                            console.print(f"[yellow]停止进一步分析以节省资源[/]")
                            break
                    except Exception as e:
                        api_error_count += 1
                        error_msg = str(e)
                        
                        # 检查是否是 API 限制或严重错误
                        if "400" in error_msg or "401" in error_msg or "403" in error_msg or "429" in error_msg:
                            console.print(f"[red]✗ API 错误，停止分析: {error_msg[:80]}[/]")
                            return None
                        
                        console.print(f"[yellow]⚠ 帧 {idx} ({minutes}:{seconds:.0f}) 分析失败: {error_msg[:50]}[/]")
                        
                        if api_error_count >= max_api_errors:
                            console.print(f"[red]✗ 连续 {max_api_errors} 次错误，停止分析[/]")
                            return None
                    
                    progress.update(task, advance=1)
            
            # 汇总结果
            is_compliant = len(all_issues) == 0
            
            # 计算评分
            severity_weights = {'low': 5, 'medium': 10, 'high': 20, 'critical': 40}
            total_penalty = sum(severity_weights.get(i.get('severity', 'low'), 5) for i in all_issues)
            overall_score = max(0, 100 - total_penalty)
            
            # 生成总结
            if is_compliant:
                summary = f"视频审核通过，共分析 {len(frames)} 帧，未发现问题。"
            else:
                summary = f"视频审核发现 {len(all_issues)} 个问题，需要修改。"
            
            return {
                'is_compliant': is_compliant,
                'overall_score': overall_score,
                'summary': summary,
                'issues': all_issues
            }
            
        except Exception as e:
            console.print(f"[red]✗ 智谱 AI 分析失败：{e}[/]")
            return None
    
    def _analyze_frames_with_qwen(self, frames, frame_timestamps: List[float]) -> Optional[Dict]:
        """使用阿里 Qwen 分析帧（复用逐帧分析逻辑，因架构通用）"""
        return self._analyze_frames_with_zhipu(frames, frame_timestamps)

    def _get_binary_sample_order(self, n: int) -> List[int]:
        """
        生成二分采样顺序的索引列表
        
        例如 n=8 时，返回顺序为: [4, 2, 6, 1, 3, 5, 7, 0]
        这样先分析中间帧，再分析四分点，逐步细化覆盖整个视频
        
        Args:
            n: 帧总数
            
        Returns:
            重排后的索引列表
        """
        if n <= 0:
            return []
        if n == 1:
            return [0]
        
        result = []
        queue = [(0, n - 1)]  # (start, end) 区间
        
        while queue:
            start, end = queue.pop(0)
            if start > end:
                continue
            
            mid = (start + end) // 2
            if mid not in result:
                result.append(mid)
            
            # 添加左右子区间
            if start < mid:
                queue.append((start, mid - 1))
            if mid < end:
                queue.append((mid + 1, end))
        
        # 确保包含所有索引
        for i in range(n):
            if i not in result:
                result.append(i)
        
        return result
    
    def review_video(self, frames, video_path: str) -> Optional[ReviewResult]:
        """
        审核视频
        
        Args:
            frames: VideoFrame 列表
            video_path: 视频文件路径
            
        Returns:
            审核结果
        """
        if not self.client:
            console.print("[red]✗ AI 客户端未初始化[/]")
            return None
        
        if not frames:
            console.print("[yellow]⚠ 没有可分析的帧[/]")
            return None
        
        console.print(f"[blue]正在进行 AI 审核，分析 {len(frames)} 帧...[/]")
        
        # 获取帧时间戳
        frame_timestamps = [f.timestamp for f in frames]
        
        # 根据提供商选择分析方法
        if self.provider == 'zhipu':
            result_data = self._analyze_frames_with_zhipu(frames, frame_timestamps)
        elif self.provider == 'qwen':
            result_data = self._analyze_frames_with_qwen(frames, frame_timestamps)
        else:
            console.print(f"[red]✗ 不支持的 AI 提供商：{self.provider}[/]")
            return None
            
        if not result_data:
            return None
        
        # 解析结果
        issues = []
        for issue_data in result_data.get('issues', []):
            frame_index = issue_data.get('frame_index', 0)
            # 将帧索引转换为时间戳
            timestamp = frame_timestamps[frame_index] if frame_index < len(frame_timestamps) else 0
            
            issues.append(Issue(
                timestamp=timestamp,
                category=issue_data.get('category', '未分类'),
                description=issue_data.get('description', ''),
                severity=issue_data.get('severity', 'low'),
                suggestion=issue_data.get('suggestion', '')
            ))
        
        is_compliant = result_data.get('is_compliant', True)
        overall_score = result_data.get('overall_score', 100)
        summary = result_data.get('summary', '')
        
        # 构建结果
        result = ReviewResult(
            video_path=video_path,
            video_filename=os.path.basename(video_path),
            is_compliant=is_compliant,
            overall_score=overall_score,
            total_frames_analyzed=len(frames),
            issues=issues,
            summary=summary,
            frame_analyses=[]
        )
        
        # 打印结果摘要
        if is_compliant:
            console.print(f"[green]✓ 审核通过！评分：{overall_score}/100[/]")
        else:
            console.print(f"[red]✗ 审核未通过！评分：{overall_score}/100[/]")
            console.print(f"[red]  发现 {len(issues)} 个问题[/]")
        
        return result
    
    def test_connection(self) -> bool:
        """测试 AI 连接"""
        if not self.client:
            return False
        
        try:
            # 智谱也支持类似的 chat.completions 接口
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "回复 'OK' 则表示连接成功"}],
                max_tokens=10
            )
            return 'OK' in response.choices[0].message.content.upper()
        except Exception as e:
            console.print(f"[red]✗ {self.provider} API 连接测试失败：{e}[/]")
            return False
