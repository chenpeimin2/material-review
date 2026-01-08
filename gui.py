#!/usr/bin/env python3
"""
Material Review GUI 启动器
使用简单的 GUI 界面来运行命令行工具
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess
import threading
import sys
import os
from pathlib import Path
import yaml

import shutil

class MaterialReviewGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Material Review - 素材视频审核工具")
        self.root.geometry("900x750")
        
        # 1. 确定运行模式和资源路径
        if getattr(sys, 'frozen', False):
            # 打包环境
            self.base_path = sys._MEIPASS
            self.main_script = os.path.join(self.base_path, 'main.py')
            self.resource_config_path = os.path.join(self.base_path, 'config.yaml')
        else:
            # 开发环境
            self.base_path = os.path.dirname(os.path.abspath(__file__))
            self.main_script = os.path.join(self.base_path, 'main.py')
            self.resource_config_path = os.path.join(self.base_path, 'config.yaml')
            
        # 2. 确定数据存储目录（解决沙盒只读问题）
        # 将数据和配置放在用户的文档目录下
        self.work_dir = os.path.join(os.path.expanduser("~"), "Documents", "MaterialReview")
        if not os.path.exists(self.work_dir):
            try:
                os.makedirs(self.work_dir)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建数据目录: {self.work_dir}\n{e}")
        
        # 3. 确定最终使用的 config.yaml 路径
        self.config_path = os.path.join(self.work_dir, 'config.yaml')
        
        # 4. 如果配置不存在，从资源目录复制一份
        if not os.path.exists(self.config_path):
            if os.path.exists(self.resource_config_path):
                try:
                    shutil.copy2(self.resource_config_path, self.config_path)
                except Exception as e:
                    messagebox.showerror("错误", f"无法初始化配置文件: {e}")
            else:
                # 连默认配置都没有，创建一个空的或者提示
                pass
        
        self.create_widgets()
        self.load_config_to_gui()
        
    def create_widgets(self):
        # 1. 标题区域
        title_frame = ttk.Frame(self.root, padding="10")
        title_frame.pack(fill=tk.X)
        
        ttk.Label(
            title_frame, 
            text="Material Review - 素材视频审核工具",
            font=("Arial", 16, "bold")
        ).pack()
        
        # 2. 主标签页容器
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # --- “运行” 标签页 ---
        run_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(run_frame, text="   运行任务   ")
        self.create_run_tab(run_frame)
        
        # --- “设置” 标签页 ---
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text="   系统设置   ")
        self.create_settings_tab(settings_frame)
        
        # 3. 底部状态栏与进度条
        status_frame = ttk.Frame(self.root, padding=(10, 5))
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.progress_bar = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, expand=True, side=tk.LEFT, padx=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="就绪", width=10, anchor="e")
        self.status_label.pack(side=tk.RIGHT)

    def create_run_tab(self, parent):
        # 分左右两栏：左侧操作，右侧日志
        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(paned, padding=(0, 0, 10, 0))
        right_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        paned.add(right_frame, weight=3)
        
        # === 左侧的操作面板 ===
        
        # A. 视频审核区
        group_review = ttk.LabelFrame(left_frame, text="视频审核", padding="10")
        group_review.pack(fill=tk.X, pady=5)
        
        ttk.Button(group_review, text="选择视频并审核", command=self.select_and_review, width=20).pack(pady=5)
        
        # 新增：一键下载并审核
        ttk.Button(group_review, text="一键下载并审核", command=self.download_and_review, width=20, style="Accent.TButton").pack(pady=5)
        
        self.download_first_var = tk.BooleanVar()
        ttk.Checkbutton(group_review, text=" 先下载邮件附件", variable=self.download_first_var).pack(pady=5, anchor="w")
        
        # B. 批量下载区
        group_download = ttk.LabelFrame(left_frame, text="批量下载", padding="10")
        group_download.pack(fill=tk.X, pady=5)
        
        ttk.Label(group_download, text="发件人筛选:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.filter_sender_var = tk.StringVar()
        ttk.Entry(group_download, textvariable=self.filter_sender_var).pack(fill=tk.X, pady=2)
        
        ttk.Label(group_download, text="日期筛选 (YYYY-MM-DD):", font=("Arial", 10, "bold")).pack(anchor="w")
        self.filter_date_var = tk.StringVar()
        ttk.Entry(group_download, textvariable=self.filter_date_var).pack(fill=tk.X, pady=2)
        
        ttk.Button(group_download, text="开始下载", command=self.start_download).pack(pady=5, fill=tk.X)
        
        # C. 工具箱
        group_tools = ttk.LabelFrame(left_frame, text="工具箱", padding="10")
        group_tools.pack(fill=tk.X, pady=5)
        
        ttk.Button(group_tools, text="测试邮箱连接", command=lambda: self.run_command([sys.executable, self.main_script, 'test-email'])).pack(pady=2, fill=tk.X)
        ttk.Button(group_tools, text="测试 AI 连接", command=lambda: self.run_command([sys.executable, self.main_script, 'test-ai'])).pack(pady=2, fill=tk.X)
        ttk.Button(group_tools, text="打开下载目录", command=self.open_downloads_dir).pack(pady=2, fill=tk.X)
        ttk.Button(group_tools, text="打开截图目录", command=self.open_screenshots_dir).pack(pady=2, fill=tk.X)
        ttk.Button(group_tools, text="打开报告目录", command=self.open_reports_dir).pack(pady=2, fill=tk.X)
        ttk.Button(group_tools, text="查看审核规则", command=self.open_config_file).pack(pady=2, fill=tk.X)
        ttk.Button(group_tools, text="清除所有缓存", command=self.clear_cache).pack(pady=2, fill=tk.X)

        # === 右侧的日志面板 ===
        ttk.Label(right_frame, text="运行日志:").pack(anchor="w")
        self.output_text = scrolledtext.ScrolledText(right_frame, height=20, font=("Courier", 11))
        self.output_text.pack(fill=tk.BOTH, expand=True)

    def create_settings_tab(self, parent):
        # 邮箱设置
        group_email = ttk.LabelFrame(parent, text="邮箱设置", padding="15")
        group_email.pack(fill=tk.X, pady=10)
        
        # 1. 邮箱类型选择
        ttk.Label(group_email, text="邮箱类型:").grid(row=0, column=0, sticky="w", pady=5)
        self.email_provider_var = tk.StringVar()
        provider_cb = ttk.Combobox(group_email, textvariable=self.email_provider_var, state="readonly", width=15)
        provider_cb['values'] = ('163 邮箱', '126 邮箱', 'QQ 邮箱', '自定义')
        provider_cb.grid(row=0, column=1, sticky="w", pady=5)
        provider_cb.bind('<<ComboboxSelected>>', self.on_provider_change)
        
        # 2. 服务器地址
        ttk.Label(group_email, text="IMAP 服务器:").grid(row=1, column=0, sticky="w", pady=5)
        self.imap_server_var = tk.StringVar()
        ttk.Entry(group_email, textvariable=self.imap_server_var, width=30).grid(row=1, column=1, sticky="w", pady=5)
        
        # 3. 账号
        ttk.Label(group_email, text="邮箱账号:").grid(row=2, column=0, sticky="w", pady=5)
        self.email_user_var = tk.StringVar()
        ttk.Entry(group_email, textvariable=self.email_user_var, width=30).grid(row=2, column=1, sticky="w", pady=5)
        
        # 4. 密码/授权码
        ttk.Label(group_email, text="授权码/密码:").grid(row=3, column=0, sticky="w", pady=5)
        self.email_pass_var = tk.StringVar()
        ttk.Entry(group_email, textvariable=self.email_pass_var, show="*", width=30).grid(row=3, column=1, sticky="w", pady=5)
        ttk.Label(group_email, text="(注意：通常使用授权码而非登录密码)", font=("Arial", 9, "italic"), foreground="gray").grid(row=3, column=2, sticky="w", padx=10)

        # 保存按钮
        ttk.Button(group_email, text="保存配置", command=self.save_config).grid(row=4, column=1, sticky="e", pady=20)

        # AI 设置 - 已隐藏
        # group_ai = ttk.LabelFrame(parent, text="AI 设置", padding="15")
        # group_ai.pack(fill=tk.X, pady=10)
        
        # 1. AI 提供商
        # ttk.Label(group_ai, text="AI 服务商:").grid(row=0, column=0, sticky="w", pady=5)
        # self.ai_provider_var = tk.StringVar()
        # ai_provider_cb = ttk.Combobox(group_ai, textvariable=self.ai_provider_var, state="readonly", width=15)
        # ai_provider_cb['values'] = ('智谱 AI (Zhipu)', '通义千问 (Qwen)')
        # ai_provider_cb.grid(row=0, column=1, sticky="w", pady=5)
        
        # 2. API Key
        # ttk.Label(group_ai, text="API Key:").grid(row=1, column=0, sticky="w", pady=5)
        # self.ai_apikey_var = tk.StringVar()
        # ttk.Entry(group_ai, textvariable=self.ai_apikey_var, show="*", width=30).grid(row=1, column=1, sticky="w", pady=5)

        # 保存按钮 (复用上面的保存逻辑，或者给 AI 单独一个保存按钮，这里统一下面给一个总的保存看起来更整洁，但为了方便，在每个group加一个也行，或者在最下面加一个总的)
        # 这里选择在最底部加一个总保存按钮
        ttk.Button(parent, text="保存所有配置", command=self.save_config, width=20).pack(pady=10)

    def on_provider_change(self, event):
        provider = self.email_provider_var.get()
        if provider == '163 邮箱':
            self.imap_server_var.set('imap.163.com')
        elif provider == '126 邮箱':
            self.imap_server_var.set('imap.126.com')
        elif provider == 'QQ 邮箱':
            self.imap_server_var.set('imap.qq.com')
        # 自定义不修改

    def load_config_to_gui(self):
        """加载配置文件到界面"""
        if not os.path.exists(self.config_path):
            return
            
        try:
            config = None
            for enc in ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'cp936']:
                try:
                    with open(self.config_path, 'r', encoding=enc) as f:
                        config = yaml.safe_load(f) or {}
                    break
                except UnicodeDecodeError:
                    continue
            if config is None:
                with open(self.config_path, 'rb') as f:
                    text = f.read().decode('utf-8', errors='replace')
                config = yaml.safe_load(text) or {}
                
            email_conf = config.get('email', {})
            self.imap_server_var.set(email_conf.get('imap_server', ''))
            self.email_user_var.set(email_conf.get('username', ''))
            self.email_pass_var.set(email_conf.get('password', ''))
            
            # 推断 Provider
            server = email_conf.get('imap_server', '')
            if '163.com' in server:
                self.email_provider_var.set('163 邮箱')
            elif '126.com' in server:
                self.email_provider_var.set('126 邮箱')
            elif 'qq.com' in server:
                self.email_provider_var.set('QQ 邮箱')
            else:
                self.email_provider_var.set('自定义')
            
            # 加载 AI 配置
            # ai_conf = config.get('ai', {})
            # provider = ai_conf.get('provider', 'zhipu')
            # if provider == 'zhipu':
            #     self.ai_provider_var.set('智谱 AI (Zhipu)')
            #     self.ai_apikey_var.set(ai_conf.get('zhipu', {}).get('api_key', ''))
            # elif provider == 'qwen':
            #     self.ai_provider_var.set('通义千问 (Qwen)')
            #     self.ai_apikey_var.set(ai_conf.get('qwen', {}).get('api_key', ''))
                
        except Exception as e:
            messagebox.showerror("错误", f"读取配置文件失败: {e}")

    def save_config(self):
        """保存配置到文件"""
        if not os.path.exists(self.config_path):
             messagebox.showerror("错误", "配置文件不存在")
             return

        try:
            # 先读取现有配置以保留其他字段
            config = None
            for enc in ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'cp936']:
                try:
                    with open(self.config_path, 'r', encoding=enc) as f:
                        config = yaml.safe_load(f) or {}
                    break
                except UnicodeDecodeError:
                    continue
            if config is None:
                with open(self.config_path, 'rb') as f:
                    text = f.read().decode('utf-8', errors='replace')
                config = yaml.safe_load(text) or {}
            
            # 更新邮箱配置
            if 'email' not in config:
                config['email'] = {}
                
            config['email']['imap_server'] = self.imap_server_var.get().strip()
            config['email']['username'] = self.email_user_var.get().strip()
            config['email']['password'] = self.email_pass_var.get().strip()
            # 默认使用 SSL 和端口 993
            config['email']['use_ssl'] = True
            config['email']['imap_port'] = 993
            
            # 更新 AI 配置
            # if 'ai' not in config:
            #     config['ai'] = {}
                
            # provider_str = self.ai_provider_var.get()
            # if '智谱' in provider_str:
            #     config['ai']['provider'] = 'zhipu'
            #     if 'zhipu' not in config['ai']: config['ai']['zhipu'] = {}
            #     config['ai']['zhipu']['api_key'] = self.ai_apikey_var.get().strip()
            # elif '千问' in provider_str:
            #     config['ai']['provider'] = 'qwen'
            #     if 'qwen' not in config['ai']: config['ai']['qwen'] = {}
            #     config['ai']['qwen']['api_key'] = self.ai_apikey_var.get().strip()
            #     # 确保 base_url 存在
            #     if 'base_url' not in config['ai']['qwen']:
            #         config['ai']['qwen']['base_url'] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
                
            messagebox.showinfo("成功", "配置已保存！")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存配置文件失败: {e}")

    def select_and_review(self):
        filename = filedialog.askopenfilename(
            title="选择要审核的视频",
            filetypes=[("视频文件", "*.mp4 *.mov *.avi *.mkv"), ("所有文件", "*.*")]
        )
        if filename:
            cmd = [sys.executable, self.main_script, 'review', '-f', filename]
            if self.download_first_var.get():
                cmd.append('--download-first')
            self.run_command(cmd)

    def download_and_review(self):
        """下载所有新视频并审核"""
        # 直接调用 review 命令并开启 --download-first，且不指定 -f 
        # (假设 main.py 支持不指定 -f 时自动处理新下载的，或者 main.py 需要适配)
        # 根据 main.py 逻辑: 
        # if download_first: 下载...
        # video_files = list_new_videos() ...
        # if not video_file: scan folder...
        # 所以直接调用即可
        
        cmd = [sys.executable, self.main_script, 'review', '--download-first']
        
        # 将发件人筛选也带上（如果设置了）
        sender = self.filter_sender_var.get().strip()
        if sender:
            cmd.extend(['--sender', sender])
            
        # 将日期筛选也带上（如果设置了）
        since = self.filter_date_var.get().strip()
        if since:
            cmd.extend(['--since', since])
            
        self.run_command(cmd)

    def start_download(self):
        cmd = [sys.executable, self.main_script, 'download']
        sender = self.filter_sender_var.get().strip()
        date = self.filter_date_var.get().strip()
        
        if sender:
            cmd.extend(['-s', sender])
        if date:
            cmd.extend(['-d', date])
            
        self.run_command(cmd)

    def clear_cache(self):
        """清除缓存"""
        if messagebox.askyesno("确认清理", "确定要清空所有报告、截图和下载的视频吗？\n\n这将删除 'reports', 'screenshots' 和 'downloads' 目录下的所有文件。"):
            # 添加 --include-downloads 标志以清理所有内容
            self.run_command([sys.executable, self.main_script, 'clean', '--include-downloads'])
    
    def _resolve_path(self, base_dir: str, path_str: str) -> str:
        ps = os.path.expanduser(os.path.expandvars(path_str or ''))
        if os.path.isabs(ps):
            return os.path.normpath(ps)
        return os.path.normpath(os.path.join(base_dir, ps if ps else '.'))
    
    def _open_dir(self, path_str: str):
        try:
            os.makedirs(path_str, exist_ok=True)
            if sys.platform == 'darwin':
                self.run_command(['open', path_str])
            elif sys.platform.startswith('win'):
                self.run_command(['explorer', path_str])
            else:
                self.run_command(['xdg-open', path_str])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开目录: {e}")
    
    def open_reports_dir(self):
        try:
            config = None
            for enc in ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'cp936']:
                try:
                    with open(self.config_path, 'r', encoding=enc) as f:
                        config = yaml.safe_load(f) or {}
                    break
                except UnicodeDecodeError:
                    continue
            if config is None:
                with open(self.config_path, 'rb') as f:
                    text = f.read().decode('utf-8', errors='replace')
                config = yaml.safe_load(text) or {}
            paths = config.get('paths', {})
            reports_dir = self._resolve_path(self.work_dir, paths.get('reports', './reports'))
            self._open_dir(reports_dir)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开报告目录: {e}")
    
    def open_downloads_dir(self):
        try:
            config = None
            for enc in ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'cp936']:
                try:
                    with open(self.config_path, 'r', encoding=enc) as f:
                        config = yaml.safe_load(f) or {}
                    break
                except UnicodeDecodeError:
                    continue
            if config is None:
                with open(self.config_path, 'rb') as f:
                    text = f.read().decode('utf-8', errors='replace')
                config = yaml.safe_load(text) or {}
            paths = config.get('paths', {})
            downloads_dir = self._resolve_path(self.work_dir, paths.get('downloads', './downloads'))
            self._open_dir(downloads_dir)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开下载目录: {e}")
    
    def open_screenshots_dir(self):
        try:
            config = None
            for enc in ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'cp936']:
                try:
                    with open(self.config_path, 'r', encoding=enc) as f:
                        config = yaml.safe_load(f) or {}
                    break
                except UnicodeDecodeError:
                    continue
            if config is None:
                with open(self.config_path, 'rb') as f:
                    text = f.read().decode('utf-8', errors='replace')
                config = yaml.safe_load(text) or {}
            paths = config.get('paths', {})
            screenshots_dir = self._resolve_path(self.work_dir, paths.get('screenshots', './screenshots'))
            self._open_dir(screenshots_dir)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开截图目录: {e}")
    
    def open_config_file(self):
        try:
            if not os.path.exists(self.config_path):
                messagebox.showerror("错误", "配置文件不存在")
                return
            if sys.platform == 'darwin':
                self.run_command(['open', self.config_path])
            elif sys.platform.startswith('win'):
                self.run_command(['explorer', self.config_path])
            else:
                self.run_command(['xdg-open', self.config_path])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开配置文件: {e}")
    

    def run_command(self, cmd):
        """运行命令并更新UI"""
        def run():
            self.output_text.insert(tk.END, f"\n🚀 正在启动: {' '.join(cmd)}\n")
            self.output_text.see(tk.END)
            
            # 开始进度条
            self.root.after(0, lambda: self.progress_bar.start(10))
            self.root.after(0, lambda: self.status_label.config(text="运行中..."))
            self.notebook.select(0) # 自动切换到运行页
            
            try:
                # 强制使用 UTF-8 环境，解决 Windows 下 GBK 编码问题
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1,
                    env=env,
                    cwd=self.work_dir  # 关键：设置工作目录为文档目录，这样 main.py 就会在这里查找 config 和创建数据目录
                )
                
                for line in process.stdout:
                    self.output_text.insert(tk.END, line)
                    self.output_text.see(tk.END)
                
                process.wait()
                
            except Exception as e:
                self.output_text.insert(tk.END, f"\n❌ 错误: {str(e)}\n")
            
            finally:
                # 停止进度条
                self.root.after(0, lambda: self.progress_bar.stop())
                self.root.after(0, lambda: self.status_label.config(text="就绪"))
                self.output_text.insert(tk.END, f"\n🏁 任务结束\n{'='*50}\n")
                self.output_text.see(tk.END)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

def main():
    if getattr(sys, 'frozen', False):
        if len(sys.argv) > 1 and sys.argv[1].endswith('main.py'):
            main_path = sys.argv[1]
            sys.argv = [main_path] + sys.argv[2:]
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("material_cli", main_path)
                cli_main = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(cli_main)
                cli_main.cli()
            except Exception as e:
                print(f"Error executing CLI: {e}")
                sys.exit(1)
            sys.exit(0)

    root = tk.Tk()
    # 尝试设置图标（如果有的话）
    # root.iconbitmap('icon.ico') 
    app = MaterialReviewGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
