"""
邮件处理模块（生产增强版）
负责连接 IMAP 邮箱、搜索邮件、下载视频附件
"""

import imaplib
import email
import hashlib
import uuid
import time
import socket
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime
from email.message import Message
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()


# =========================
# 数据结构
# =========================

@dataclass
class EmailInfo:
    email_id: str
    subject: str
    sender: str
    date: datetime
    attachments: List[str]


@dataclass
class DownloadedAttachment:
    video_id: str
    original_filename: str
    stored_filename: str
    filepath: str
    size: int
    sha256: str
    email_subject: str
    email_sender: str
    email_date: datetime


# =========================
# 核心处理类
# =========================

class EmailHandler:

    VIDEO_EXTENSIONS = {
        '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'
    }

    MAX_ATTACHMENT_SIZE = 1024 * 1024 * 1024  # 1GB 上限

    def __init__(self, config: dict):
        self.imap_server = config.get('imap_server', 'imap.163.com')
        self.imap_port = config.get('imap_port', 993)
        self.username = config['username']
        self.password = config['password']
        self.filter_config = config.get('filter', {})
        self.connection: Optional[imaplib.IMAP4_SSL] = None

        if 'ID' not in imaplib.Commands:
            imaplib.Commands['ID'] = ('AUTH',)

    # =========================
    # 连接管理
    # =========================

    def connect(self) -> bool:
        try:
            console.print(f"[blue]连接 IMAP：{self.imap_server}[/]")
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.username, self.password)
            self._send_id()
            try:
                self.connection.select('INBOX')
            except Exception:
                pass
            console.print("[green]✓ 邮箱连接成功[/]")
            return True
        except Exception as e:
            console.print(f"[red]✗ 邮箱连接失败：{e}[/]")
            return False

    def disconnect(self):
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None

    def _send_id(self):
        try:
            args = '("name" "VideoReviewBot" "version" "1.0")'
            self.connection._simple_command('ID', args)
        except Exception:
            pass

    # =========================
    # 辅助方法：安全 Fetch
    # =========================
    
    def _safe_fetch(self, email_id, message_parts, retries=3):
        """带有重试机制的 Fetch"""
        for attempt in range(retries):
            try:
                if self.connection is None:
                    if not self.connect():
                        raise ConnectionError("无法连接到 IMAP 服务器")
                
                # 检查 email_id 类型，如果是 str 则编码为 bytes
                eid = email_id.encode() if isinstance(email_id, str) else email_id
                
                return self.connection.fetch(eid, message_parts)
                
            except (imaplib.IMAP4.abort, socket.error, ConnectionResetError, BrokenPipeError) as e:
                console.print(f"[yellow]⚠ 连接中断 ({e})，正在重试 ({attempt+1}/{retries})...[/]")
                self.disconnect()
                time.sleep(2)
                # 重新连接
                if attempt < retries - 1:
                    self.connect()
                    # 重新选择 INBOX
                    try:
                        self.connection.select('INBOX')
                    except:
                        pass
        
        raise ConnectionError(f"在 {retries} 次尝试后 fetching 失败")

    # =========================
    # 搜索邮件
    # =========================

    def search_emails(
        self,
        sender: Optional[str] = None,
        since_date: Optional[str] = None,
        subject_contains: Optional[str] = None,
        only_with_video: bool = True
    ) -> List[EmailInfo]:
        if not self.connection:
            return []

        criteria = []

        # 优先使用传入参数，否则使用配置文件中的过滤条件
        sender = sender or self.filter_config.get('sender')
        since_date = since_date or self.filter_config.get('since_date')
        subject_contains = subject_contains or self.filter_config.get('subject_contains')

        if sender:
            criteria += ['FROM', sender]

        if since_date:
            dt = datetime.strptime(since_date, '%Y-%m-%d')
            criteria += ['SINCE', dt.strftime('%d-%b-%Y')]

        if subject_contains:
            criteria += ['SUBJECT', subject_contains]

        if not criteria:
            criteria = ['ALL']
            
        try:
            status, data = self.connection.search(None, *criteria)
        except Exception:
            # 搜索失败尝试重连一次
            self.disconnect()
            self.connect()
            status, data = self.connection.search(None, *criteria)

        if status != 'OK':
            return []

        results = []
        email_ids = data[0].split()
        
        if not email_ids:
            return []

        # 获取扫描上限（防止扫描万封邮件）
        max_scan = 50 
        
        # 逆序排列，从最新的邮件开始扫
        email_ids = email_ids[::-1]
        
        total_to_scan = min(len(email_ids), max_scan)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("正在扫描邮件附件...", total=total_to_scan)
            
            for i in range(total_to_scan):
                email_id = email_ids[i]
                
                try:
                    # 使用 safe_fetch 替代直接 fetch
                    status, msg_data = self._safe_fetch(email_id, '(RFC822)')
                except Exception as e:
                    console.print(f"[red]获取邮件 {email_id} 失败: {e}[/]")
                    progress.update(task, advance=1)
                    continue
                    
                if status != 'OK':
                    progress.update(task, advance=1)
                    continue

                msg = email.message_from_bytes(msg_data[0][1])

                attachments = self._extract_attachment_names(msg)
                
                # 如果需要筛选视频且没有视频附件，跳过
                if only_with_video and not any(self._is_video(f) for f in attachments):
                    progress.update(task, advance=1)
                    continue

                results.append(EmailInfo(
                    email_id=email_id.decode(),
                    subject=self._decode(msg.get('Subject')),
                    sender=self._decode(msg.get('From')),
                    date=self._parse_date(msg.get('Date')),
                    attachments=attachments
                ))
                
                progress.update(task, advance=1)

        console.print(f"[green]✓ 扫描完成，找到 {len(results)} 封含视频附件邮件[/]")
        return results

    # =========================
    # 下载附件
    # =========================

    def download_attachments(self, email_id: str, save_dir: str, only_video: bool = True) -> List[DownloadedAttachment]:
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        try:
            status, msg_data = self._safe_fetch(email_id, '(RFC822)')
        except Exception as e:
            console.print(f"[red]下载邮件 {email_id} 内容失败: {e}[/]")
            return []
            
        if status != 'OK':
            return []

        msg = email.message_from_bytes(msg_data[0][1])

        downloaded = []

        for part in msg.walk():
            filename = part.get_filename()
            if not filename:
                continue

            filename = self._decode(filename)
            if not self._is_video(filename):
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue

            # 使用安全文件名
            subject = self._decode(msg.get('Subject')) or 'unknown'
            safe_subject = re.sub(r'[\\/*?:"<>|]', '', subject)
            safe_subject = safe_subject.strip()[:50]
            if not safe_subject:
                safe_subject = 'unknown'
            
            ext = Path(filename).suffix.lower()
            video_id = str(uuid.uuid4())
            short_id = video_id[:8]
            
            stored_name = f"{safe_subject}_{short_id}{ext}"
            filepath = save_path / stored_name
            
            # 校验大小限制
            if len(payload) > self.MAX_ATTACHMENT_SIZE:
                console.print(f"[yellow]跳过超大文件：{filename}[/]")
                continue

            # 写入文件
            try:
                with open(filepath, 'wb') as f:
                    f.write(payload)
            except Exception as e:
                console.print(f"[red]写入文件失败: {e}[/]")
                continue

            sha256 = hashlib.sha256(payload).hexdigest()
            
            downloaded.append(DownloadedAttachment(
                video_id=video_id,
                original_filename=filename,
                stored_filename=stored_name,
                filepath=str(filepath),
                size=len(payload),
                sha256=sha256,
                email_subject=self._decode(msg.get('Subject')),
                email_sender=self._decode(msg.get('From')),
                email_date=self._parse_date(msg.get('Date'))
            ))

            console.print(f"[green]✓ 下载完成：{filename}[/]")

        return downloaded

    # =========================
    # 工具方法
    # =========================

    def _extract_attachment_names(self, msg: Message) -> List[str]:
        names = []
        for part in msg.walk():
            name = part.get_filename()
            if name:
                names.append(self._decode(name))
        return names

    def _is_video(self, filename: str) -> bool:
        return Path(filename).suffix.lower() in self.VIDEO_EXTENSIONS

    def _decode(self, value: str) -> str:
        if not value:
            return ''
        parts = decode_header(value)
        return ''.join(
            p.decode(c or 'utf-8', errors='ignore') if isinstance(p, bytes) else p
            for p, c in parts
        )

    def _parse_date(self, value: str) -> datetime:
        try:
            return parsedate_to_datetime(value)
        except Exception:
            return datetime.now()
