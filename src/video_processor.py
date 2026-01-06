"""
视频处理模块
负责提取视频帧、生成截图、获取视频信息
"""

import cv2
import os
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import timedelta

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()


@dataclass
class VideoInfo:
    """视频信息"""
    filepath: str
    filename: str
    duration: float  # 秒
    fps: float
    width: int
    height: int
    frame_count: int
    file_size: int  # 字节


@dataclass
class VideoFrame:
    """视频帧"""
    timestamp: float  # 秒
    frame_index: int
    image_data: bytes  # JPEG 编码的图片数据
    width: int
    height: int
    
    def to_base64(self) -> str:
        """转换为 base64 编码"""
        return base64.b64encode(self.image_data).decode('utf-8')
    
    def save(self, filepath: str) -> str:
        """保存为文件"""
        with open(filepath, 'wb') as f:
            f.write(self.image_data)
        return filepath


class VideoProcessor:
    """视频处理器"""
    
    def __init__(self, config: dict = None):
        """
        初始化视频处理器
        
        Args:
            config: 视频处理配置
        """
        self.config = config or {}
        # 支持两种配置方式：
        # 1. extract_fps: 每秒提取几帧 (推荐，如 extract_fps=2 表示每秒2帧)
        # 2. frame_interval: 每隔几秒提取一帧 (旧方式，向后兼容)
        self.extract_fps = self.config.get('extract_fps', None)  # 每秒抽帧数
        self.frame_interval = self.config.get('frame_interval', 1)  # 每X秒提取一帧（旧方式）
        self.max_frames = self.config.get('max_frames', 200)  # 最大帧数
        self.grid_cols = self.config.get('grid_cols', 4)  # 拼图列数
        self.cell_width = self.config.get('cell_width', 640)  # 每个单元格宽度
        self.supported_formats = self.config.get('supported_formats', 
            ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'])
    
    def is_supported(self, filepath: str) -> bool:
        """检查是否为支持的视频格式"""
        ext = Path(filepath).suffix.lower()
        return ext in self.supported_formats
    
    def get_video_info(self, video_path: str) -> Optional[VideoInfo]:
        """
        获取视频信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频信息对象，失败返回 None
        """
        if not os.path.exists(video_path):
            console.print(f"[red]✗ 视频文件不存在：{video_path}[/]")
            return None
        
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                console.print(f"[red]✗ 无法打开视频：{video_path}[/]")
                return None
            
            # 获取视频属性
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # 计算时长
            duration = frame_count / fps if fps > 0 else 0
            
            # 获取文件大小
            file_size = os.path.getsize(video_path)
            
            cap.release()
            
            return VideoInfo(
                filepath=video_path,
                filename=Path(video_path).name,
                duration=duration,
                fps=fps,
                width=width,
                height=height,
                frame_count=frame_count,
                file_size=file_size
            )
            
        except Exception as e:
            console.print(f"[red]✗ 获取视频信息失败：{e}[/]")
            return None
    
    def extract_frames(self, 
                       video_path: str, 
                       interval_seconds: Optional[float] = None,
                       fps: Optional[float] = None,
                       max_frames: Optional[int] = None) -> List[VideoFrame]:
        """
        提取视频关键帧
        
        Args:
            video_path: 视频文件路径
            interval_seconds: 提取间隔（秒），与 fps 二选一
            fps: 每秒提取帧数（推荐），与 interval_seconds 二选一
            max_frames: 最大帧数，默认使用配置值
            
        Returns:
            提取的帧列表
        """
        max_count = max_frames or self.max_frames
        
        # 确定抽帧间隔：优先使用参数，其次使用配置
        if fps is not None:
            interval = 1.0 / fps
        elif interval_seconds is not None:
            interval = interval_seconds
        elif self.extract_fps is not None:
            interval = 1.0 / self.extract_fps
        else:
            interval = self.frame_interval
        
        video_info = self.get_video_info(video_path)
        if not video_info:
            return []
        
        # 计算实际 fps 用于日志显示
        actual_fps = 1.0 / interval if interval > 0 else 0
        console.print(f"[blue]正在提取视频帧：{video_info.filename}[/]")
        console.print(f"[dim]视频时长：{self._format_duration(video_info.duration)}，抽帧频率：{actual_fps:.1f} fps（每 {interval:.2f} 秒一帧）[/]")
        console.print(f"[dim]分辨率：{video_info.width}x{video_info.height}[/]")
        
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return []
            
            frames = []
            video_fps = video_info.fps
            total_frames = video_info.frame_count
            
            # 计算需要提取的时间点
            timestamps = []
            current_time = 0
            while current_time < video_info.duration and len(timestamps) < max_count:
                timestamps.append(current_time)
                current_time += interval
            
            # 确保包含最后一帧（如果视频足够长）
            if video_info.duration > interval and len(timestamps) > 0 and timestamps[-1] < video_info.duration - 1:
                timestamps.append(video_info.duration - 0.5)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("提取帧中...", total=len(timestamps))
                
                for timestamp in timestamps:
                    # 跳转到指定时间点
                    frame_pos = int(timestamp * video_fps)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                    
                    ret, frame = cap.read()
                    if not ret:
                        progress.update(task, advance=1)
                        continue
                    
                    # 编码为 JPEG
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    image_data = buffer.tobytes()
                    
                    frames.append(VideoFrame(
                        timestamp=timestamp,
                        frame_index=frame_pos,
                        image_data=image_data,
                        width=frame.shape[1],
                        height=frame.shape[0]
                    ))
                    
                    progress.update(task, advance=1)
            
            cap.release()
            console.print(f"[green]✓ 成功提取 {len(frames)} 帧[/]")
            return frames
            
        except Exception as e:
            console.print(f"[red]✗ 提取帧失败：{e}[/]")
            return []
    
    def extract_frames_scene_change(self, 
                                    video_path: str, 
                                    threshold: float = 30.0,
                                    min_interval: float = 0.1,
                                    max_frames: Optional[int] = None) -> List[VideoFrame]:
        """
        基于场景变化检测提取帧
        只在画面发生显著变化时才提取帧，避免漏掉快速变化的内容
        
        Args:
            video_path: 视频文件路径
            threshold: 场景变化阈值（0-100），越小越敏感，默认30
            min_interval: 最小采样间隔（秒），防止过于频繁，默认0.1秒
            max_frames: 最大帧数，默认使用配置值
            
        Returns:
            提取的帧列表
        """
        max_count = max_frames or self.max_frames
        
        video_info = self.get_video_info(video_path)
        if not video_info:
            return []
        
        console.print(f"[blue]正在提取视频帧（场景变化检测模式）：{video_info.filename}[/]")
        console.print(f"[dim]视频时长：{self._format_duration(video_info.duration)}[/]")
        console.print(f"[dim]分辨率：{video_info.width}x{video_info.height}[/]")
        console.print(f"[dim]阈值：{threshold}，最小间隔：{min_interval}s[/]")
        
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return []
            
            frames = []
            fps = video_info.fps
            total_frames = video_info.frame_count
            min_frame_gap = int(min_interval * fps)  # 最小帧间隔
            
            prev_frame = None
            prev_hist = None
            frame_idx = 0
            last_captured_idx = -min_frame_gap  # 确保第一帧可以被捕获
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("场景检测中...", total=total_frames)
                
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # 计算当前帧的直方图
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
                    cv2.normalize(hist, hist)
                    
                    should_capture = False
                    
                    # 第一帧总是捕获
                    if prev_hist is None:
                        should_capture = True
                    else:
                        # 计算直方图差异
                        diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
                        
                        # 如果差异超过阈值且距离上次捕获足够远
                        if diff > threshold and (frame_idx - last_captured_idx) >= min_frame_gap:
                            should_capture = True
                    
                    if should_capture and len(frames) < max_count:
                        timestamp = frame_idx / fps
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        
                        frames.append(VideoFrame(
                            timestamp=timestamp,
                            frame_index=frame_idx,
                            image_data=buffer.tobytes(),
                            width=frame.shape[1],
                            height=frame.shape[0]
                        ))
                        last_captured_idx = frame_idx
                    
                    prev_hist = hist
                    frame_idx += 1
                    
                    # 更新进度
                    if frame_idx % 30 == 0:  # 每30帧更新一次进度
                        progress.update(task, completed=frame_idx)
                
                progress.update(task, completed=total_frames)
            
            cap.release()
            
            # 确保最后一帧也被捕获（如果没有的话）
            if frames and frames[-1].timestamp < video_info.duration - 1:
                last_frame = self.get_frame_at_timestamp(video_path, video_info.duration - 0.5)
                if last_frame and len(frames) < max_count:
                    frames.append(last_frame)
            
            console.print(f"[green]✓ 成功提取 {len(frames)} 帧（场景变化检测）[/]")
            return frames
            
        except Exception as e:
            console.print(f"[red]✗ 场景检测提取失败：{e}[/]")
            return []
    
    def capture_screenshot(self, 
                          video_path: str, 
                          timestamp: float, 
                          output_path: Optional[str] = None) -> Optional[str]:
        """
        在指定时间点截取视频截图
        
        Args:
            video_path: 视频文件路径
            timestamp: 时间点（秒）
            output_path: 输出路径，为 None 则自动生成
            
        Returns:
            截图文件路径，失败返回 None
        """
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                console.print(f"[red]✗ 无法打开视频[/]")
                return None
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_pos = int(timestamp * fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                console.print(f"[red]✗ 无法读取帧[/]")
                return None
            
            # 生成输出路径
            if output_path is None:
                video_name = Path(video_path).stem
                output_path = f"{video_name}_screenshot_{timestamp:.1f}s.jpg"
            
            # 确保目录存在
            output_dir = Path(output_path).parent
            if output_dir != Path('.'):
                output_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存截图
            cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            console.print(f"[green]✓ 已截图：{output_path} (时间点 {self._format_duration(timestamp)})[/]")
            return output_path
            
        except Exception as e:
            console.print(f"[red]✗ 截图失败：{e}[/]")
            return None
    
    def capture_screenshots_batch(self,
                                  video_path: str,
                                  timestamps: List[float],
                                  output_dir: str) -> List[Tuple[float, str]]:
        """
        批量截取视频截图
        
        Args:
            video_path: 视频文件路径
            timestamps: 时间点列表（秒）
            output_dir: 输出目录
            
        Returns:
            (时间点, 截图路径) 列表
        """
        results = []
        video_name = Path(video_path).stem
        
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return []
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            for timestamp in timestamps:
                frame_pos = int(timestamp * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # 生成文件名
                safe_timestamp = str(timestamp).replace('.', '_')
                filename = f"{video_name}_{safe_timestamp}s.jpg"
                output_path = os.path.join(output_dir, filename)
                
                cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                results.append((timestamp, output_path))
            
            cap.release()
            console.print(f"[green]✓ 批量截图完成，共 {len(results)} 张[/]")
            return results
            
        except Exception as e:
            console.print(f"[red]✗ 批量截图失败：{e}[/]")
            return []
    
    def get_frame_at_timestamp(self, video_path: str, timestamp: float) -> Optional[VideoFrame]:
        """
        获取指定时间点的帧（不保存文件）
        
        Args:
            video_path: 视频文件路径
            timestamp: 时间点（秒）
            
        Returns:
            VideoFrame 对象，失败返回 None
        """
        try:
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                return None
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_pos = int(timestamp * fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return None
            
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            return VideoFrame(
                timestamp=timestamp,
                frame_index=frame_pos,
                image_data=buffer.tobytes(),
                width=frame.shape[1],
                height=frame.shape[0]
            )
            
        except Exception as e:
            return None
    
    def _format_duration(self, seconds: float) -> str:
        """格式化时长"""
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def create_frame_grid(self, 
                          frames: List[VideoFrame], 
                          cols: Optional[int] = None,
                          cell_width: Optional[int] = None,
                          show_timestamp: bool = True) -> List[Tuple[bytes, List[float]]]:
        """
        将多帧合并成网格图（拼图）
        
        可以显著减少 AI API 调用次数：例如 4x4=16 帧合成一张图，
        原本需要 16 次 API 调用，现在只需 1 次。
        
        Args:
            frames: VideoFrame 列表
            cols: 每行列数，默认使用配置或 4
            cell_width: 每个单元格宽度（像素），默认使用配置或 640
            show_timestamp: 是否在每帧上显示时间戳标签
            
        Returns:
            列表，每个元素是 (grid_image_bytes, timestamps_in_grid)
        """
        import numpy as np
        
        if not frames:
            return []
        
        cols = cols or self.grid_cols
        cell_width = cell_width or self.cell_width
        
        # 计算网格布局
        rows = cols  # 正方形网格比较稳
        frames_per_grid = cols * rows
        
        # 计算单元格高度（保持原始宽高比）
        sample_frame = frames[0]
        aspect_ratio = sample_frame.height / sample_frame.width
        cell_height = int(cell_width * aspect_ratio)
        
        grids = []
        
        # 分批处理帧
        for batch_start in range(0, len(frames), frames_per_grid):
            batch_frames = frames[batch_start:batch_start + frames_per_grid]
            batch_timestamps = [f.timestamp for f in batch_frames]
            
            # 创建空白画布
            grid_width = cols * cell_width
            actual_rows = (len(batch_frames) + cols - 1) // cols
            grid_height = actual_rows * cell_height
            grid_image = np.zeros((grid_height, grid_width, 3), dtype=np.uint8)
            
            for i, frame in enumerate(batch_frames):
                row = i // cols
                col = i % cols
                
                # 解码帧图像
                nparr = np.frombuffer(frame.image_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if img is None:
                    continue
                
                # 缩放到单元格大小
                img_resized = cv2.resize(img, (cell_width, cell_height))
                
                # 添加时间戳标签
                if show_timestamp:
                    minutes = int(frame.timestamp // 60)
                    seconds = frame.timestamp % 60
                    label = f"{minutes}:{seconds:05.2f}"
                    
                    # 绘制标签背景
                    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                    cv2.rectangle(img_resized, (2, 2), (label_size[0] + 8, label_size[1] + 8), (0, 0, 0), -1)
                    # 绘制标签文字
                    cv2.putText(img_resized, label, (5, label_size[1] + 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # 放置到网格中
                y_start = row * cell_height
                y_end = y_start + cell_height
                x_start = col * cell_width
                x_end = x_start + cell_width
                grid_image[y_start:y_end, x_start:x_end] = img_resized
            
            # 编码为 JPEG
            _, buffer = cv2.imencode('.jpg', grid_image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            grids.append((buffer.tobytes(), batch_timestamps))
        
        console.print(f"[green]✓ 已将 {len(frames)} 帧合并为 {len(grids)} 张网格图（{cols}x{rows}）[/]")
        return grids

    def save_grid_images(self, 
                         grids: List[Tuple[bytes, List[float]]], 
                         output_dir: str, 
                         basename: str = "grid") -> List[str]:
        """
        将生成的网格图保存为文件
        
        Args:
            grids: create_frame_grid 返回的网格数据列表
            output_dir: 保存目录
            basename: 文件名前缀
            
        Returns:
            保存的文件路径列表
        """
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        
        for i, (image_bytes, timestamps) in enumerate(grids):
            time_str = f"{timestamps[0]:.1f}s_{timestamps[-1]:.1f}s"
            filename = f"{basename}_{i+1:02d}_{time_str}.jpg"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            
            paths.append(filepath)
            console.print(f"  已保存网格图: [dim]{filepath}[/]")
            
        return paths

    def annotate_image_file(self, image_path: str, label: str, output_path: Optional[str] = None) -> Optional[str]:
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            h, w = img.shape[:2]
            band_h = max(30, int(h * 0.12))
            overlay = img.copy()
            cv2.rectangle(overlay, (0, 0), (w, band_h), (0, 0, 255), -1)
            alpha = 0.35
            img = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.8
            thickness = 2
            cv2.putText(img, label[:60], (16, int(band_h*0.7)), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)
            if output_path is None:
                p = Path(image_path)
                output_path = str(p.with_name(p.stem + "_marked" + p.suffix))
            cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
            return output_path
        except Exception:
            return None

    def save_frame_nearest(self, 
                           frames: List[VideoFrame], 
                           target_timestamp: float, 
                           output_dir: str,
                           filename_prefix: str) -> Optional[str]:
        if not frames:
            return None
        nearest = min(frames, key=lambda f: abs(f.timestamp - target_timestamp))
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        target_str = f"{target_timestamp:.2f}".replace('.', '_')
        nearest_str = f"{nearest.timestamp:.2f}".replace('.', '_')
        filename = f"{filename_prefix}_{target_str}s_nearest_{nearest_str}s.jpg"
        out = os.path.join(output_dir, filename)
        with open(out, 'wb') as f:
            f.write(nearest.image_data)
        return out
