"""
报告生成模块
负责生成审核报告（HTML/Markdown 格式）
"""

import os
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from jinja2 import Template
from rich.console import Console

console = Console()


# HTML 报告模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - 审核报告</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 10px;
        }
        
        .header .subtitle {
            font-size: 14px;
            opacity: 0.8;
        }
        
        .score-section {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 40px;
            background: #f8f9fa;
            border-bottom: 1px solid #eee;
        }
        
        .score-circle {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: white;
            font-weight: bold;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        
        .score-circle.pass {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        
        .score-circle.fail {
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
        }
        
        .score-circle .score {
            font-size: 48px;
            line-height: 1;
        }
        
        .score-circle .label {
            font-size: 14px;
            margin-top: 8px;
            opacity: 0.9;
        }
        
        .status-badge {
            margin-left: 30px;
            text-align: center;
        }
        
        .status-badge .badge {
            display: inline-block;
            padding: 12px 24px;
            border-radius: 30px;
            font-size: 18px;
            font-weight: 600;
        }
        
        .status-badge .badge.pass {
            background: #d4edda;
            color: #155724;
        }
        
        .status-badge .badge.fail {
            background: #f8d7da;
            color: #721c24;
        }
        
        .section {
            padding: 30px 40px;
            border-bottom: 1px solid #eee;
        }
        
        .section:last-child {
            border-bottom: none;
        }
        
        .section-title {
            font-size: 18px;
            font-weight: 600;
            color: #1a1a2e;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
        }
        
        .section-title::before {
            content: '';
            width: 4px;
            height: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 2px;
            margin-right: 12px;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }
        
        .info-item {
            display: flex;
            flex-direction: column;
        }
        
        .info-item .label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        
        .info-item .value {
            font-size: 14px;
            color: #1a1a2e;
            font-weight: 500;
        }
        
        .summary-text {
            line-height: 1.8;
            color: #444;
            font-size: 15px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
        }
        
        .issue-list {
            list-style: none;
        }
        
        .issue-item {
            background: #fff;
            border: 1px solid #eee;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }
        
        .issue-header {
            display: flex;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .severity-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            margin-right: 12px;
        }
        
        .severity-badge.low {
            background: #fff3cd;
            color: #856404;
        }
        
        .severity-badge.medium {
            background: #ffeaa7;
            color: #9a7b00;
        }
        
        .severity-badge.high {
            background: #f8d7da;
            color: #721c24;
        }
        
        .severity-badge.critical {
            background: #dc3545;
            color: white;
        }
        
        .issue-category {
            font-size: 14px;
            color: #666;
        }
        
        .issue-timestamp {
            margin-left: auto;
            font-size: 13px;
            color: #888;
            background: #f0f0f0;
            padding: 4px 10px;
            border-radius: 15px;
        }
        
        .issue-description {
            font-size: 15px;
            color: #333;
            line-height: 1.6;
            margin-bottom: 12px;
        }
        
        .issue-suggestion {
            font-size: 14px;
            color: #666;
            background: #f8f9fa;
            padding: 12px;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }
        
        .issue-suggestion strong {
            color: #667eea;
        }
        
        .screenshot {
            margin-top: 15px;
        }
        
        .screenshot img {
            max-width: 100%;
            border-radius: 8px;
            border: 1px solid #eee;
        }
        
        .no-issues {
            text-align: center;
            padding: 40px;
            background: #d4edda;
            border-radius: 12px;
            color: #155724;
        }
        
        .no-issues .icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
        
        .footer {
            text-align: center;
            padding: 20px;
            color: #888;
            font-size: 12px;
            background: #f8f9fa;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ company_name }}</h1>
            <p class="subtitle">素材视频审核报告</p>
        </div>
        
        <div class="score-section">
            <div class="score-circle {{ 'pass' if is_compliant else 'fail' }}">
                <span class="score">{{ overall_score }}</span>
                <span class="label">综合评分</span>
            </div>
            <div class="status-badge">
                <span class="badge {{ 'pass' if is_compliant else 'fail' }}">
                    {{ '✓ 审核通过' if is_compliant else '✗ 审核未通过' }}
                </span>
                <p style="margin-top: 10px; color: #666; font-size: 13px;">
                    共发现 {{ issues|length }} 个问题
                </p>
            </div>
        </div>
        
        <div class="section">
            <h2 class="section-title">视频信息</h2>
            <div class="info-grid">
                <div class="info-item">
                    <span class="label">文件名</span>
                    <span class="value">{{ video_filename }}</span>
                </div>
                <div class="info-item">
                    <span class="label">视频时长</span>
                    <span class="value">{{ video_duration }}</span>
                </div>
                <div class="info-item">
                    <span class="label">分析帧数</span>
                    <span class="value">{{ total_frames }} 帧</span>
                </div>
                <div class="info-item">
                    <span class="label">审核时间</span>
                    <span class="value">{{ review_time }}</span>
                </div>
                {% if email_sender %}
                <div class="info-item">
                    <span class="label">发件人</span>
                    <span class="value">{{ email_sender }}</span>
                </div>
                {% endif %}
                {% if email_subject %}
                <div class="info-item">
                    <span class="label">邮件主题</span>
                    <span class="value">{{ email_subject }}</span>
                </div>
                {% endif %}
            </div>
        </div>
        
        {% if summary %}
        <div class="section">
            <h2 class="section-title">审核总结</h2>
            <div class="summary-text">{{ summary }}</div>
        </div>
        {% endif %}
        
        <div class="section">
            <h2 class="section-title">问题详情</h2>
            {% if issues %}
            <ul class="issue-list">
                {% for issue in issues %}
                <li class="issue-item">
                    <div class="issue-header">
                        <span class="severity-badge {{ issue.severity }}">{{ issue.severity }}</span>
                        <span class="issue-category">{{ issue.category }}</span>
                        <span class="issue-timestamp">⏱ {{ issue.timestamp_formatted }}</span>
                    </div>
                    <div class="issue-description">{{ issue.description }}</div>
                    {% if issue.suggestion %}
                    <div class="issue-suggestion">
                        <strong>建议：</strong>{{ issue.suggestion }}
                    </div>
                    {% endif %}
                    {% if issue.screenshot_base64 %}
                    <div class="screenshot">
                        <img src="data:image/jpeg;base64,{{ issue.screenshot_base64 }}" alt="问题截图">
                    </div>
                    {% endif %}
                </li>
                {% endfor %}
            </ul>
            {% else %}
            <div class="no-issues">
                <div class="icon">🎉</div>
                <p><strong>恭喜！未发现任何问题</strong></p>
                <p>该视频素材符合所有审核标准</p>
            </div>
            {% endif %}
        </div>
        
        <div class="footer">
            由 AI 素材审核系统自动生成 · {{ review_time }}
        </div>
    </div>
</body>
</html>
"""


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, config: dict = None):
        """
        初始化报告生成器
        
        Args:
            config: 报告配置
        """
        self.config = config or {}
        self.report_format = self.config.get('format', 'html')
        self.embed_screenshots = self.config.get('embed_screenshots', True)
        self.company_name = self.config.get('company_name', '素材审核系统')
    
    def generate_html_report(self,
                            review_result,
                            video_info = None,
                            email_info: dict = None,
                            screenshots: dict = None,
                            output_path: Optional[str] = None) -> str:
        """
        生成 HTML 报告
        
        Args:
            review_result: ReviewResult 对象
            video_info: VideoInfo 对象（可选）
            email_info: 邮件信息字典（可选）
            screenshots: 问题截图字典 {timestamp: filepath}（可选）
            output_path: 输出路径（可选）
            
        Returns:
            报告文件路径
        """
        # 准备模板数据
        template_data = {
            'title': review_result.video_filename,
            'company_name': self.company_name,
            'is_compliant': review_result.is_compliant,
            'overall_score': int(review_result.overall_score),
            'video_filename': review_result.video_filename,
            'total_frames': review_result.total_frames_analyzed,
            'review_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'summary': review_result.summary,
            'issues': [],
            'video_duration': '',
            'email_sender': '',
            'email_subject': ''
        }
        
        # 视频信息
        if video_info:
            template_data['video_duration'] = self._format_duration(video_info.duration)
        
        # 邮件信息
        if email_info:
            template_data['email_sender'] = email_info.get('sender', '')
            template_data['email_subject'] = email_info.get('subject', '')
        
        # 处理问题列表
        for issue in review_result.issues:
            issue_data = {
                'severity': issue.severity,
                'category': issue.category,
                'description': issue.description,
                'suggestion': issue.suggestion,
                'timestamp_formatted': self._format_duration(issue.timestamp),
                'screenshot_base64': ''
            }
            
            # 添加截图
            if screenshots and self.embed_screenshots:
                screenshot_path = screenshots.get(issue.timestamp)
                if screenshot_path and os.path.exists(screenshot_path):
                    with open(screenshot_path, 'rb') as f:
                        issue_data['screenshot_base64'] = base64.b64encode(f.read()).decode('utf-8')
            
            template_data['issues'].append(issue_data)
        
        # 渲染模板
        template = Template(HTML_TEMPLATE)
        html_content = template.render(**template_data)
        
        # 确定输出路径
        if output_path is None:
            video_name = Path(review_result.video_filename).stem
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"{video_name}_审核报告_{timestamp}.html"
        
        # 确保目录存在
        output_dir = Path(output_path).parent
        if output_dir != Path('.') and str(output_dir) != '':
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存报告
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        console.print(f"[green]✓ 报告已生成：{output_path}[/]")
        return output_path
    
    def generate_markdown_report(self,
                                review_result,
                                video_info = None,
                                email_info: dict = None,
                                screenshots: dict = None,
                                output_path: Optional[str] = None) -> str:
        """
        生成 Markdown 报告
        
        Args:
            review_result: ReviewResult 对象
            video_info: VideoInfo 对象（可选）
            email_info: 邮件信息字典（可选）
            screenshots: 问题截图字典 {timestamp: filepath}（可选）
            output_path: 输出路径（可选）
            
        Returns:
            报告文件路径
        """
        lines = []
        
        # 标题
        lines.append(f"# {self.company_name} - 审核报告")
        lines.append("")
        lines.append(f"**文件名**: {review_result.video_filename}")
        lines.append(f"**审核时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 审核结果
        lines.append("## 审核结果")
        lines.append("")
        status = "✅ 通过" if review_result.is_compliant else "❌ 未通过"
        lines.append(f"- **状态**: {status}")
        lines.append(f"- **评分**: {int(review_result.overall_score)}/100")
        lines.append(f"- **问题数量**: {len(review_result.issues)}")
        lines.append("")
        
        # 视频信息
        if video_info:
            lines.append("## 视频信息")
            lines.append("")
            lines.append(f"- **时长**: {self._format_duration(video_info.duration)}")
            lines.append(f"- **分辨率**: {video_info.width}x{video_info.height}")
            lines.append(f"- **分析帧数**: {review_result.total_frames_analyzed}")
            lines.append("")
        
        # 邮件信息
        if email_info:
            lines.append("## 邮件信息")
            lines.append("")
            if email_info.get('sender'):
                lines.append(f"- **发件人**: {email_info['sender']}")
            if email_info.get('subject'):
                lines.append(f"- **主题**: {email_info['subject']}")
            lines.append("")
        
        # 审核总结
        if review_result.summary:
            lines.append("## 审核总结")
            lines.append("")
            lines.append(review_result.summary)
            lines.append("")
        
        # 问题详情
        lines.append("## 问题详情")
        lines.append("")
        
        if review_result.issues:
            for i, issue in enumerate(review_result.issues, 1):
                severity_map = {
                    'low': '🟡 轻微',
                    'medium': '🟠 中等',
                    'high': '🔴 严重',
                    'critical': '⛔ 极严重'
                }
                severity_text = severity_map.get(issue.severity, issue.severity)
                
                lines.append(f"### 问题 {i}")
                lines.append("")
                lines.append(f"- **严重程度**: {severity_text}")
                lines.append(f"- **类别**: {issue.category}")
                lines.append(f"- **时间点**: {self._format_duration(issue.timestamp)}")
                lines.append(f"- **描述**: {issue.description}")
                if issue.suggestion:
                    lines.append(f"- **建议**: {issue.suggestion}")
                
                # 截图
                if screenshots:
                    screenshot_path = screenshots.get(issue.timestamp)
                    if screenshot_path and os.path.exists(screenshot_path):
                        # 使用相对路径
                        lines.append(f"- **截图**: ![问题截图]({screenshot_path})")
                
                lines.append("")
        else:
            lines.append("🎉 **恭喜！未发现任何问题**")
            lines.append("")
        
        # 组合内容
        content = '\n'.join(lines)
        
        # 确定输出路径
        if output_path is None:
            video_name = Path(review_result.video_filename).stem
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"{video_name}_审核报告_{timestamp}.md"
        
        # 确保目录存在
        output_dir = Path(output_path).parent
        if output_dir != Path('.') and str(output_dir) != '':
            output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存报告
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        console.print(f"[green]✓ 报告已生成：{output_path}[/]")
        return output_path
    
    def generate_report(self,
                       review_result,
                       video_info = None,
                       email_info: dict = None,
                       screenshots: dict = None,
                       output_path: Optional[str] = None) -> str:
        """
        生成报告（根据配置选择格式）
        
        Args:
            review_result: ReviewResult 对象
            video_info: VideoInfo 对象（可选）
            email_info: 邮件信息字典（可选）
            screenshots: 问题截图字典 {timestamp: filepath}（可选）
            output_path: 输出路径（可选）
            
        Returns:
            报告文件路径
        """
        if self.report_format == 'markdown' or self.report_format == 'md':
            return self.generate_markdown_report(
                review_result, video_info, email_info, screenshots, output_path
            )
        else:
            return self.generate_html_report(
                review_result, video_info, email_info, screenshots, output_path
            )
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
