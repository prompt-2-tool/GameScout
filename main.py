#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GameScout - 游戏采集工具
主程序入口
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import json
import os
import sys
from datetime import datetime
import logging
import atexit
import signal

from modules.port_detector import PortDetector
from modules.game_scraper import GameScraper
from modules.azgames_scraper import AzGamesScraper
from modules.armorgames_scraper import ArmorGamesScraper
from modules.geoguessr_scraper import GeoGuessrScraper
from modules.data_manager import DataManager


class GameScoutApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GameScout v2.6 - 游戏采集工具")
        self.root.geometry("800x600")

        # 注册清理函数
        self.register_cleanup_handlers()

        # 设置图标
        try:
            # 获取程序所在目录
            if getattr(sys, 'frozen', False):
                # 如果是打包后的exe
                base_path = sys._MEIPASS
            else:
                # 如果是开发环境
                base_path = os.path.dirname(os.path.abspath(__file__))

            icon_path = os.path.join(base_path, "logo.ico")
            if os.path.exists(icon_path):
                # 尝试多种方法设置图标
                try:
                    self.root.iconbitmap(icon_path)
                except:
                    # 如果iconbitmap失败，尝试使用PhotoImage
                    try:
                        from PIL import Image, ImageTk
                        img = Image.open(icon_path)
                        img = img.resize((32, 32), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self.root.iconphoto(False, photo)
                        # 保持引用避免被垃圾回收
                        self.root._icon_photo = photo
                    except:
                        # 最后尝试使用wm_iconbitmap
                        try:
                            self.root.wm_iconbitmap(icon_path)
                        except:
                            pass
        except Exception as e:
            print(f"图标加载失败: {e}")  # 调试信息

        # 初始化组件
        self.port_detector = PortDetector()
        self.game_scraper = GameScraper()
        self.azgames_scraper = None  # 按需创建
        self.data_manager = DataManager()

        # 设置日志
        self.setup_logging()

        # 创建界面
        self.create_widgets()

        # 初始化端口
        self.detect_port()

    def register_cleanup_handlers(self):
        """注册程序退出时的清理处理器"""
        # 注册atexit清理函数
        atexit.register(self.cleanup_on_exit)

        # 注册信号处理器（Windows）
        try:
            signal.signal(signal.SIGTERM, self.signal_handler)
            signal.signal(signal.SIGINT, self.signal_handler)
        except AttributeError:
            # 某些信号在Windows上可能不可用
            pass

        # 注册窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"接收到信号 {signum}，开始清理...")
        self.cleanup_on_exit()
        sys.exit(0)

    def on_closing(self):
        """窗口关闭事件处理"""
        self.logger.info("程序正在关闭，清理资源...")
        self.cleanup_on_exit()
        self.root.destroy()

    def cleanup_on_exit(self):
        """程序退出时的清理函数"""
        try:
            # 停止所有采集活动
            self.is_scraping = False

            # 清理所有scraper实例
            scrapers_to_clean = [
                ('game_scraper', self.game_scraper),
                ('azgames_scraper', self.azgames_scraper),
                ('current_scraper', getattr(self, 'current_scraper', None))
            ]

            for name, scraper in scrapers_to_clean:
                if scraper:
                    try:
                        # 尝试多种停止方法
                        if hasattr(scraper, 'stop'):
                            scraper.stop()
                        elif hasattr(scraper, 'stop_scraping'):
                            scraper.stop_scraping()

                        # 如果有driver属性，确保关闭
                        if hasattr(scraper, 'driver') and scraper.driver:
                            try:
                                scraper.driver.quit()
                            except:
                                pass

                        self.logger.debug(f"已清理 {name}")
                    except Exception as e:
                        self.logger.error(f"清理 {name} 时出错: {str(e)}")

            # 强制垃圾回收
            import gc
            gc.collect()

            self.logger.info("资源清理完成")

        except Exception as e:
            # 清理过程中的错误不应该阻止程序退出
            print(f"清理过程中出错: {str(e)}")
            pass

    def setup_logging(self):
        """设置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()  # 只输出到控制台，不创建日志文件
            ]
        )
        self.logger = logging.getLogger(__name__)

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)  # 版权信息行不扩展
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # 版权信息
        copyright_frame = ttk.Frame(self.root)
        copyright_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))

        # 获取当前年份
        import datetime
        current_year = datetime.datetime.now().year

        # 创建版权信息框架
        copyright_text_frame = ttk.Frame(copyright_frame)
        copyright_text_frame.pack()

        # 普通文本部分
        ttk.Label(copyright_text_frame, text=f"© {current_year} ",
                 font=('Arial', 8), foreground='gray').pack(side=tk.LEFT)

        # 可点击的链接部分
        link_label = ttk.Label(copyright_text_frame, text="prompt2tool.com",
                              font=('Arial', 8), foreground='blue', cursor='hand2')
        link_label.pack(side=tk.LEFT)
        link_label.bind("<Button-1>", self.open_website)
        link_label.bind("<Enter>", lambda e: link_label.configure(foreground='darkblue'))
        link_label.bind("<Leave>", lambda e: link_label.configure(foreground='blue'))

        # 通用设置框架
        settings_frame = ttk.LabelFrame(main_frame, text="通用设置", padding="10")
        settings_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        settings_frame.columnconfigure(1, weight=1)

        # 端口设置
        ttk.Label(settings_frame, text="端口设置:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.port_var = tk.StringVar(value="7897")
        port_frame = ttk.Frame(settings_frame)
        port_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Entry(port_frame, textvariable=self.port_var, width=10).pack(side=tk.LEFT)
        ttk.Button(port_frame, text="检测端口", command=self.detect_port).pack(side=tk.LEFT, padx=(5, 0))

        # 采集数量设置
        ttk.Label(settings_frame, text="采集数量:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.max_games_var = tk.StringVar(value="0")
        games_frame = ttk.Frame(settings_frame)
        games_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Entry(games_frame, textvariable=self.max_games_var, width=10).pack(side=tk.LEFT)
        ttk.Label(games_frame, text="个游戏 (默认0不限制，设置数字限制采集数量)").pack(side=tk.LEFT, padx=(5, 0))

        # 手动获取
        ttk.Label(settings_frame, text="手动获取:").grid(row=2, column=0, sticky=tk.W, pady=5)
        iframe_frame = ttk.Frame(settings_frame)
        iframe_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        iframe_frame.columnconfigure(0, weight=1)

        self.manual_url_var = tk.StringVar()
        manual_url_entry = ttk.Entry(iframe_frame, textvariable=self.manual_url_var, width=50)
        manual_url_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        ttk.Button(iframe_frame, text="获取",
                  command=self.get_manual_iframe).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(settings_frame, text="支持平台:", foreground="gray").grid(row=3, column=0, sticky=tk.W, pady=(0, 5))
        ttk.Label(settings_frame, text="Itch, AzGames, ArmorGames, GeoGuessr，更多平台详见下方工具页面",
                 foreground="gray").grid(row=3, column=1, sticky=tk.W, pady=(0, 5))

        # 创建标签页
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 创建itch.io标签页
        self.create_itch_tab()

        # 创建azgames.io标签页
        self.create_azgames_tab()

        # 创建armorgames.com标签页
        self.create_armorgames_tab()

        # 创建geoguessr.io标签页
        self.create_geoguessr_tab()

        # 创建工具集标签页
        self.create_tools_tab()

        # 创建功能标签页
        self.create_function_tab()

        # 初始化变量
        self.scraping_thread = None
        self.is_scraping = False
        self.current_scraper = None

    def create_itch_tab(self):
        """创建itch.io标签页"""
        itch_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(itch_frame, text="Itch")

        # 配置网格权重
        itch_frame.columnconfigure(1, weight=1)
        itch_frame.rowconfigure(2, weight=1)

        # 采集按钮
        button_frame = ttk.Frame(itch_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        ttk.Button(button_frame, text="开始采集Itch",
                  command=lambda: self.start_scraping('itch')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="停止采集",
                  command=self.stop_scraping).pack(side=tk.LEFT, padx=5)

        # 状态标签
        self.itch_status_label = ttk.Label(itch_frame, text="就绪", foreground="green")
        self.itch_status_label.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        # 日志文本框
        log_frame = ttk.LabelFrame(itch_frame, text="采集日志", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.itch_log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.itch_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 按钮框架
        itch_button_frame = ttk.Frame(itch_frame)
        itch_button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)

        ttk.Button(itch_button_frame, text="查看Itch数据",
                  command=lambda: self.view_data('itch.io')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(itch_button_frame, text="清空日志",
                  command=lambda: self.clear_log('itch')).pack(side=tk.LEFT, padx=5)

    def create_azgames_tab(self):
        """创建azgames.io标签页"""
        azgames_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(azgames_frame, text="AzGames")

        # 配置网格权重
        azgames_frame.columnconfigure(1, weight=1)
        azgames_frame.rowconfigure(2, weight=1)

        # 采集按钮
        button_frame = ttk.Frame(azgames_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        ttk.Button(button_frame, text="开始采集AzGames",
                  command=lambda: self.start_scraping('azgames')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="停止采集",
                  command=self.stop_scraping).pack(side=tk.LEFT, padx=5)

        # 状态标签
        self.azgames_status_label = ttk.Label(azgames_frame, text="就绪", foreground="green")
        self.azgames_status_label.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        # 日志文本框
        log_frame = ttk.LabelFrame(azgames_frame, text="采集日志", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.azgames_log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.azgames_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 按钮框架
        azgames_button_frame = ttk.Frame(azgames_frame)
        azgames_button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)

        ttk.Button(azgames_button_frame, text="查看AzGames数据",
                  command=lambda: self.view_data('azgames.io')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(azgames_button_frame, text="清空日志",
                  command=lambda: self.clear_log('azgames')).pack(side=tk.LEFT, padx=5)



    def create_armorgames_tab(self):
        """创建armorgames.com标签页"""
        armorgames_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(armorgames_frame, text="ArmorGames")

        # 配置网格权重
        armorgames_frame.columnconfigure(1, weight=1)
        armorgames_frame.rowconfigure(2, weight=1)

        # 采集按钮
        button_frame = ttk.Frame(armorgames_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        ttk.Button(button_frame, text="开始采集ArmorGames",
                  command=lambda: self.start_scraping('armorgames')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="停止采集",
                  command=self.stop_scraping).pack(side=tk.LEFT, padx=5)

        # 状态标签
        self.armorgames_status_label = ttk.Label(armorgames_frame, text="就绪", foreground="green")
        self.armorgames_status_label.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        # 日志文本框
        log_frame = ttk.LabelFrame(armorgames_frame, text="采集日志", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.armorgames_log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.armorgames_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 按钮框架
        armorgames_button_frame = ttk.Frame(armorgames_frame)
        armorgames_button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)

        ttk.Button(armorgames_button_frame, text="查看ArmorGames数据",
                  command=lambda: self.view_data('armorgames.com')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(armorgames_button_frame, text="清空日志",
                  command=lambda: self.clear_log('armorgames')).pack(side=tk.LEFT, padx=5)

    def create_geoguessr_tab(self):
        """创建geoguessr.io标签页"""
        geoguessr_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(geoguessr_frame, text="GeoGuessr")

        # 配置网格权重
        geoguessr_frame.columnconfigure(1, weight=1)
        geoguessr_frame.rowconfigure(2, weight=1)

        # 采集按钮
        button_frame = ttk.Frame(geoguessr_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        ttk.Button(button_frame, text="开始采集GeoGuessr",
                  command=lambda: self.start_scraping('geoguessr')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="停止采集",
                  command=self.stop_scraping).pack(side=tk.LEFT, padx=5)

        # 状态标签
        self.geoguessr_status_label = ttk.Label(geoguessr_frame, text="就绪", foreground="green")
        self.geoguessr_status_label.grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        # 日志文本框
        log_frame = ttk.LabelFrame(geoguessr_frame, text="采集日志", padding="5")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.geoguessr_log_text = scrolledtext.ScrolledText(log_frame, height=15, width=70)
        self.geoguessr_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 按钮框架
        geoguessr_button_frame = ttk.Frame(geoguessr_frame)
        geoguessr_button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)

        ttk.Button(geoguessr_button_frame, text="查看GeoGuessr数据",
                  command=lambda: self.view_data('geoguessr.io')).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(geoguessr_button_frame, text="清空日志",
                  command=lambda: self.clear_log('geoguessr')).pack(side=tk.LEFT, padx=5)




    def create_tools_tab(self):
        """创建工具标签页"""
        tools_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tools_frame, text="工具")

        # 配置网格权重
        tools_frame.columnconfigure(0, weight=1)
        tools_frame.columnconfigure(1, weight=1)

        # 通用工具
        general_frame = ttk.LabelFrame(tools_frame, text="通用工具", padding="10")
        general_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        general_frame.columnconfigure(0, weight=1)
        general_frame.columnconfigure(1, weight=1)

        # 通用工具列表
        general_tools = [
            ("Iframe检测工具", "https://prompt2tool.com/tools/development/iframe-compatibility-tester", "检测网页iframe兼容性和可嵌入性"),
            ("Embed代码生成器", "https://prompt2tool.com/tools/development/iframe-embed-code-generator", "生成标准的iframe嵌入代码")
        ]

        for i, (tool_name, tool_url, tool_desc) in enumerate(general_tools):
            col = i % 2

            tool_container = ttk.Frame(general_frame)
            tool_container.grid(row=0, column=col, sticky=(tk.W, tk.E), padx=10, pady=5)
            tool_container.columnconfigure(0, weight=1)

            tool_link = ttk.Label(tool_container, text=tool_name,
                                 font=('Arial', 10, 'bold'), foreground='blue', cursor='hand2')
            tool_link.grid(row=0, column=0, sticky=tk.W)
            tool_link.bind("<Button-1>", lambda e, url=tool_url: self.open_tool_url(url))
            tool_link.bind("<Enter>", lambda e, label=tool_link: label.configure(foreground='darkblue'))
            tool_link.bind("<Leave>", lambda e, label=tool_link: label.configure(foreground='blue'))

            tool_btn = ttk.Button(tool_container, text="打开工具",
                                 command=lambda url=tool_url: self.open_tool_url(url))
            tool_btn.grid(row=1, column=0, pady=(3, 0))

            ttk.Label(tool_container, text=tool_desc,
                     font=('Arial', 8), foreground='gray').grid(row=2, column=0, sticky=tk.W, pady=(3, 0))

        # 手动游戏提取工具
        platform_frame = ttk.LabelFrame(tools_frame, text="手动游戏提取工具", padding="8")
        platform_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        platform_frame.columnconfigure(0, weight=1)
        platform_frame.columnconfigure(1, weight=1)
        platform_frame.columnconfigure(2, weight=1)

        # 游戏平台工具列表
        platform_tools = [
            ("Itch游戏提取", "https://prompt2tool.com/tools/development/itch-game-iframe-extractor"),
            ("AzGames游戏提取", "https://prompt2tool.com/tools/development/az-games-iframe-extractor"),
            ("ArmorGames游戏提取", "https://prompt2tool.com/tools/development/iframe-compatibility-tester"),
            ("CrazyGames游戏提取", "https://prompt2tool.com/tools/development/crazygames-iframe-extractor"),
            ("Y8游戏提取", "https://prompt2tool.com/tools/development/y8-iframe-extractor"),
            ("GeoGuessr游戏提取", "https://prompt2tool.com/tools/development/geoguessr-iframe-extractor")
        ]

        # 按3列布局排列，更紧凑
        for i, (tool_name, tool_url) in enumerate(platform_tools):
            row = i // 3
            col = i % 3

            tool_container = ttk.Frame(platform_frame)
            tool_container.grid(row=row, column=col, sticky=(tk.W, tk.E), padx=3, pady=3)
            tool_container.columnconfigure(0, weight=1)

            if tool_url:  # 有URL的工具
                tool_link = ttk.Label(tool_container, text=tool_name,
                                     font=('Arial', 9, 'bold'), foreground='blue', cursor='hand2')
                tool_link.grid(row=0, column=0, sticky=tk.W)
                tool_link.bind("<Button-1>", lambda e, url=tool_url: self.open_tool_url(url))
                tool_link.bind("<Enter>", lambda e, label=tool_link: label.configure(foreground='darkblue'))
                tool_link.bind("<Leave>", lambda e, label=tool_link: label.configure(foreground='blue'))

                tool_btn = ttk.Button(tool_container, text="打开",
                                     command=lambda url=tool_url: self.open_tool_url(url))
                tool_btn.grid(row=1, column=0, pady=(2, 0))
            else:  # 暂未提供的工具
                tool_label = ttk.Label(tool_container, text=tool_name,
                                      font=('Arial', 9, 'bold'), foreground='gray')
                tool_label.grid(row=0, column=0, sticky=tk.W)

                unavailable_label = ttk.Label(tool_container, text="暂未提供",
                                            font=('Arial', 8), foreground='red')
                unavailable_label.grid(row=1, column=0, pady=(2, 0))

    def open_tool_url(self, url):
        """打开工具URL"""
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开链接: {str(e)}")

    def create_function_tab(self):
        """创建导出标签页"""
        function_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(function_frame, text="导出")

        # 配置网格权重
        function_frame.columnconfigure(0, weight=1)
        function_frame.rowconfigure(2, weight=1)

        # 导出选项框架
        options_frame = ttk.LabelFrame(function_frame, text="导出选项", padding="10")
        options_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        options_frame.columnconfigure(1, weight=1)

        # 数据范围选择
        ttk.Label(options_frame, text="数据范围:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)

        self.export_range_var = tk.StringVar(value="recent")
        range_frame = ttk.Frame(options_frame)
        range_frame.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        ttk.Radiobutton(range_frame, text="本次新增（最近24小时）", variable=self.export_range_var,
                       value="recent").pack(side=tk.LEFT, padx=(0, 20))
        ttk.Radiobutton(range_frame, text="全量数据", variable=self.export_range_var,
                       value="all").pack(side=tk.LEFT)

        # 平台选择
        ttk.Label(options_frame, text="选择平台:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)

        platform_frame = ttk.Frame(options_frame)
        platform_frame.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        self.platform_vars = {
            'itch.io': tk.BooleanVar(value=True),
            'azgames.io': tk.BooleanVar(value=True),
            'armorgames.com': tk.BooleanVar(value=True),
            'geoguessr.io': tk.BooleanVar(value=True)
        }

        # 将平台复选框分两行显示，每行最多3个
        row = 0
        col = 0
        for platform, var in self.platform_vars.items():
            platform_display = platform.replace('.io', '').replace('.com', '').title()
            ttk.Checkbutton(platform_frame, text=platform_display, variable=var).grid(row=row, column=col, sticky=tk.W, padx=(0, 15), pady=2)
            col += 1
            if col >= 3:  # 每行最多3个
                col = 0
                row += 1

        # 模板选择
        ttk.Label(options_frame, text="选择模板:", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)

        template_frame = ttk.Frame(options_frame)
        template_frame.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)

        # 提供多个prompt模板选项
        prompt_templates = {
            "标准版": """学习下demo.php、开发指南.md，然后严格按照demo.php以及开发指南.md，帮我开发下面这个游戏页面（只要创建一个文件，不需要创建变体，不可以有源站的广告）：
{name_label}： {name}
FAQ等信息参考：{url}
<iframe>引入链接：{iframe_embed_url}""",

            "简洁版": """按照demo.php和开发指南.md开发游戏页面（单文件，无广告，需联网调研）：
游戏名称：{name}
参考页面：{url}
游戏链接：{iframe_embed_url}""",

            "详细版": """请学习demo.php、开发指南.md的开发规范，严格按照其中的要求帮我开发下面这个游戏页面：

要求：
- 只创建一个PHP文件，不需要创建变体
- 不可以包含源站的广告内容
- 必须联网调研分析用户需求和游戏特点
- 严格遵循开发指南中的技术规范

游戏信息：
{name_label}：{name}
FAQ等信息参考：{url}
<iframe>引入链接：{iframe_embed_url}""",

            "专业版": """基于demo.php模板和开发指南.md规范，开发以下游戏页面：

📋 开发要求：
• 单文件输出，无变体
• 移除源站广告
• 联网调研用户需求
• 遵循技术规范

🎮 游戏详情：
• 名称：{name}
• 参考：{url}
• 嵌入：{iframe_embed_url}""",

            "极简版": """开发游戏页面（参考demo.php和开发指南.md）：
{name} | {url} | {iframe_embed_url}"""
        }

        self.template_var = tk.StringVar(value="标准版")
        template_combo = ttk.Combobox(template_frame, textvariable=self.template_var,
                                     values=list(prompt_templates.keys()), state="readonly", width=15)
        template_combo.pack(side=tk.LEFT)
        template_combo.bind('<<ComboboxSelected>>', lambda e: self.update_prompt_template(prompt_templates))

        # Prompt内容显示
        ttk.Label(function_frame, text="Prompt内容:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=(10, 5))

        self.prompt_text = scrolledtext.ScrolledText(function_frame, height=8, width=80, wrap=tk.WORD)
        self.prompt_text.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        self.prompt_text.insert('1.0', prompt_templates["标准版"])

        # 存储模板字典供后续使用
        self.prompt_templates = prompt_templates
        self.current_prompt_template = prompt_templates["标准版"]

        # 添加字段标签设置（保持兼容性）
        self.field_labels = {
            'name': tk.StringVar(value='游戏名称'),
            'url': tk.StringVar(value='参考链接'),
            'iframe_url': tk.StringVar(value='iframe链接'),
            'embed_url': tk.StringVar(value='embed链接')
        }

        # 功能按钮
        button_frame = ttk.Frame(function_frame)
        button_frame.grid(row=3, column=0, pady=10)

        ttk.Button(button_frame, text="预览Prompt",
                  command=self.preview_prompts).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="导出全量数据",
                  command=lambda: self.export_prompts(recent_only=False)).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="导出本次新增",
                  command=lambda: self.export_prompts(recent_only=True)).pack(side=tk.LEFT, padx=10)

    def update_prompt_template(self, templates):
        """更新prompt模板"""
        selected_template = self.template_var.get()
        if selected_template in templates:
            # 更新当前模板内容
            self.current_prompt_template = templates[selected_template]
            # 更新文本框显示
            self.prompt_text.delete('1.0', tk.END)
            self.prompt_text.insert('1.0', templates[selected_template])

    def log_message(self, message, platform=None):
        """在日志区域显示消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        # 根据平台选择对应的日志区域
        if platform == 'itch':
            self.itch_log_text.insert(tk.END, log_entry)
            self.itch_log_text.see(tk.END)
        elif platform == 'azgames':
            self.azgames_log_text.insert(tk.END, log_entry)
            self.azgames_log_text.see(tk.END)
        elif platform == 'armorgames':
            self.armorgames_log_text.insert(tk.END, log_entry)
            self.armorgames_log_text.see(tk.END)
        elif platform == 'geoguessr':
            self.geoguessr_log_text.insert(tk.END, log_entry)
            self.geoguessr_log_text.see(tk.END)
        else:
            # 如果没有指定平台，记录到所有日志区域
            if hasattr(self, 'itch_log_text'):
                self.itch_log_text.insert(tk.END, log_entry)
                self.itch_log_text.see(tk.END)
            if hasattr(self, 'azgames_log_text'):
                self.azgames_log_text.insert(tk.END, log_entry)
                self.azgames_log_text.see(tk.END)
            if hasattr(self, 'armorgames_log_text'):
                self.armorgames_log_text.insert(tk.END, log_entry)
                self.armorgames_log_text.see(tk.END)
            if hasattr(self, 'geoguessr_log_text'):
                self.geoguessr_log_text.insert(tk.END, log_entry)
                self.geoguessr_log_text.see(tk.END)

        self.root.update_idletasks()

        # 同时记录到日志文件
        self.logger.info(message)

    def detect_port(self):
        """检测可用端口"""
        try:
            port = int(self.port_var.get())
            if self.port_detector.is_port_available(port):
                self.log_message(f"端口 {port} 可用")
            else:
                available_port = self.port_detector.find_available_port(port)
                self.port_var.set(str(available_port))
                self.log_message(f"端口 {port} 不可用，自动切换到端口 {available_port}")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的端口号")

    def start_scraping(self, platform):
        """开始采集"""
        if self.is_scraping:
            return

        self.is_scraping = True
        self.current_platform = platform

        # 根据平台设置UI状态
        if platform == 'itch':
            self.itch_status_label.config(text="正在采集...", foreground="orange")
            self.current_scraper = self.game_scraper
        elif platform == 'azgames':
            self.azgames_status_label.config(text="正在采集...", foreground="orange")
            # 创建AzGames采集器实例
            max_games = self.get_max_games()
            self.current_scraper = AzGamesScraper(max_games_limit=max_games)
        elif platform == 'armorgames':
            self.armorgames_status_label.config(text="正在采集...", foreground="orange")
            # 创建ArmorGames采集器实例
            max_games = self.get_max_games()
            self.current_scraper = ArmorGamesScraper(max_games_limit=max_games)
        elif platform == 'geoguessr':
            self.geoguessr_status_label.config(text="正在采集...", foreground="orange")
            # 创建GeoGuessr采集器实例
            max_games = self.get_max_games()
            self.current_scraper = GeoGuessrScraper(max_games_limit=max_games)


        # 在新线程中运行采集
        self.scraping_thread = threading.Thread(target=self.run_scraping, args=(platform,))
        self.scraping_thread.daemon = True
        self.scraping_thread.start()

    def stop_scraping(self):
        """停止采集"""
        self.is_scraping = False
        if self.current_scraper:
            if hasattr(self.current_scraper, 'stop'):
                self.current_scraper.stop()
            elif hasattr(self.current_scraper, 'stop_scraping'):
                self.current_scraper.stop_scraping()
        self.log_message("正在停止采集...", self.current_platform)

    def get_max_games(self):
        """获取用户设定的采集数量"""
        try:
            max_games = int(self.max_games_var.get())
            if max_games <= 0:
                max_games = None  # 0表示不限制
        except ValueError:
            max_games = None  # 默认值改为不限制
            self.max_games_var.set("0")
            self.log_message("采集数量设置无效，使用默认值0（不限制）", self.current_platform)
        return max_games

    def run_scraping(self, platform):
        """运行采集任务"""
        try:
            max_games = self.get_max_games()

            # 设置采集器的最大数量
            if max_games is not None:
                self.current_scraper.max_games_limit = max_games
                self.log_message(f"开始采集 {platform} 游戏数据，限制数量: {max_games}", platform)
            else:
                self.current_scraper.max_games_limit = None
                self.log_message(f"开始采集 {platform} 游戏数据，不限制数量", platform)

            # 设置回调函数
            def progress_callback(message, count=None):
                self.log_message(message, platform)
                if count is not None:
                    stats_text = f"已采集: {count}"
                    if max_games is not None:
                        stats_text += f"/{max_games}"
                    stats_text += " 个游戏"

                    if platform == 'itch':
                        self.itch_status_label.config(text=stats_text, foreground="blue")
                    elif platform == 'azgames':
                        self.azgames_status_label.config(text=stats_text, foreground="blue")
                    elif platform == 'armorgames':
                        self.armorgames_status_label.config(text=stats_text, foreground="blue")
                    elif platform == 'geoguessr':
                        self.geoguessr_status_label.config(text=stats_text, foreground="blue")

            # 开始采集
            if platform == 'itch':
                games = self.current_scraper.scrape_games(
                    progress_callback=progress_callback,
                    stop_flag=lambda: not self.is_scraping
                )
            elif platform == 'azgames':
                games = self.current_scraper.scrape_games(
                    progress_callback=progress_callback,
                    stop_flag=lambda: not self.is_scraping
                )
            elif platform == 'armorgames':
                games = self.current_scraper.scrape_games(
                    progress_callback=progress_callback,
                    stop_flag=lambda: not self.is_scraping
                )
            elif platform == 'geoguessr':
                games = self.current_scraper.scrape_games(
                    progress_callback=progress_callback,
                    stop_flag=lambda: not self.is_scraping
                )


            # 保存数据
            if games:
                save_result = self.data_manager.save_games(games, platform=platform)
                total = save_result.get('total', len(games))
                saved = save_result.get('saved', 0)
                duplicates = save_result.get('duplicates', 0)

                if duplicates > 0:
                    self.log_message(f"采集完成，共获取 {total} 个游戏，新增 {saved} 个，跳过重复 {duplicates} 个", platform)
                else:
                    self.log_message(f"采集完成，共获取 {total} 个游戏，全部为新游戏", platform)
            else:
                self.log_message("采集完成，本次未获取到新游戏数据", platform)

        except Exception as e:
            self.log_message(f"采集过程中发生错误: {str(e)}", platform)
            self.logger.error(f"采集错误: {str(e)}", exc_info=True)
        finally:
            # 重置界面状态
            self.is_scraping = False
            if platform == 'itch':
                self.itch_status_label.config(text="采集完成", foreground="green")
            elif platform == 'azgames':
                self.azgames_status_label.config(text="采集完成", foreground="green")
            elif platform == 'armorgames':
                self.armorgames_status_label.config(text="采集完成", foreground="green")
            elif platform == 'geoguessr':
                self.geoguessr_status_label.config(text="采集完成", foreground="green")


    def view_data(self, platform=None):
        """查看采集的数据"""
        games = self.data_manager.load_games(platform=platform)
        if not games:
            platform_name = platform if platform else "所有平台"
            messagebox.showinfo("信息", f"暂无{platform_name}的采集数据")
            return

        # 创建数据查看窗口
        data_window = tk.Toplevel(self.root)
        platform_title = f" - {platform}" if platform else ""
        data_window.title(f"采集数据查看{platform_title}")
        data_window.geometry("800x500")

        # 创建树形视图
        tree = ttk.Treeview(data_window, columns=("name", "url", "embed_url", "platform"), show="headings")
        tree.heading("name", text="游戏名称")
        tree.heading("url", text="游戏页面")
        tree.heading("embed_url", text="游戏地址")
        tree.heading("platform", text="平台")

        # 设置列宽
        tree.column("name", width=150)
        tree.column("url", width=200)
        tree.column("embed_url", width=300)
        tree.column("platform", width=100)

        # 添加数据
        for game in games:
            tree.insert("", tk.END, values=(
                game.get("name", ""),
                game.get("url", ""),
                game.get("embed_url", "") or game.get("iframe_url", ""),
                game.get("platform", "")
            ))

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def export_data(self, platform=None):
        """导出数据"""
        try:
            # 创建导出选项对话框
            export_window = tk.Toplevel(self.root)
            export_window.title("导出选项")
            export_window.geometry("400x250")
            export_window.resizable(False, False)

            # 设置窗口图标
            try:
                export_window.iconbitmap("logo.ico")
            except:
                pass

            # 设置窗口居中
            export_window.transient(self.root)
            export_window.grab_set()

            # 创建主框架
            main_frame = ttk.Frame(export_window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # 平台信息
            platform_display = platform.replace('.io', '').replace('.com', '').title() if platform else "全部平台"
            ttk.Label(main_frame, text=f"导出 {platform_display} 数据",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            # 导出范围选择
            range_var = tk.StringVar(value="all")
            ttk.Label(main_frame, text="导出范围:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))

            ttk.Radiobutton(main_frame, text="导出全部数据", variable=range_var,
                           value="all").pack(anchor=tk.W, padx=20)
            ttk.Radiobutton(main_frame, text="仅导出最近24小时新增数据", variable=range_var,
                           value="recent").pack(anchor=tk.W, padx=20, pady=(5, 0))

            # 导出格式选择
            format_var = tk.StringVar(value="json")
            ttk.Label(main_frame, text="导出格式:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(20, 5))

            ttk.Radiobutton(main_frame, text="JSON格式", variable=format_var,
                           value="json").pack(anchor=tk.W, padx=20)
            ttk.Radiobutton(main_frame, text="CSV格式", variable=format_var,
                           value="csv").pack(anchor=tk.W, padx=20, pady=(5, 0))

            # 按钮框架
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(30, 0))

            def do_export():
                recent_only = range_var.get() == "recent"
                export_format = format_var.get()

                export_window.destroy()

                # 执行导出
                filename = self.data_manager.export_games(
                    platform=platform,
                    format=export_format,
                    recent_only=recent_only
                )

                if filename:
                    range_text = "最近24小时" if recent_only else "全部"
                    platform_name = f"{platform_display} " if platform else ""
                    messagebox.showinfo("成功", f"{platform_name}{range_text}数据已导出到:\n{filename}")
                else:
                    range_text = "最近24小时" if recent_only else ""
                    platform_name = f"{platform_display} " if platform else ""
                    messagebox.showwarning("警告", f"没有{platform_name}{range_text}数据可导出")

            ttk.Button(button_frame, text="开始导出",
                      command=do_export).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="取消",
                      command=export_window.destroy).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")

    def clear_log(self, platform=None):
        """清空日志"""
        if platform == 'itch':
            self.itch_log_text.delete(1.0, tk.END)
        elif platform == 'azgames':
            self.azgames_log_text.delete(1.0, tk.END)
        elif platform == 'armorgames':
            self.armorgames_log_text.delete(1.0, tk.END)
        elif platform == 'geoguessr':
            self.geoguessr_log_text.delete(1.0, tk.END)
        else:
            # 清空所有日志
            if hasattr(self, 'itch_log_text'):
                self.itch_log_text.delete(1.0, tk.END)
            if hasattr(self, 'azgames_log_text'):
                self.azgames_log_text.delete(1.0, tk.END)
            if hasattr(self, 'armorgames_log_text'):
                self.armorgames_log_text.delete(1.0, tk.END)
            if hasattr(self, 'geoguessr_log_text'):
                self.geoguessr_log_text.delete(1.0, tk.END)

    def preview_prompts(self):
        """预览生成的prompts"""
        try:
            # 根据用户选择的数据范围获取游戏数据
            data_range = self.export_range_var.get()
            if data_range == "recent":
                games = self.get_recent_unique_games()
                range_desc = "本次新增（最近24小时）"
            else:
                games = self.get_unique_games()
                range_desc = "全量数据"

            if not games:
                messagebox.showinfo("信息", f"暂无{range_desc}游戏数据")
                return

            # 获取选中的平台信息
            selected_platforms = []
            for platform, var in self.platform_vars.items():
                if var.get():
                    platform_display = platform.replace('.io', '').replace('.com', '').title()
                    selected_platforms.append(platform_display)

            if not selected_platforms:
                platform_desc = "所有平台"
            else:
                platform_desc = ", ".join(selected_platforms)

            # 生成prompts
            prompts = self.generate_prompts(games)

            # 创建预览窗口
            preview_window = tk.Toplevel(self.root)
            preview_window.title(f"Prompt预览 - {range_desc} - {platform_desc}")
            preview_window.geometry("800x600")

            # 创建文本区域
            text_area = scrolledtext.ScrolledText(preview_window, wrap=tk.WORD)
            text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # 添加头部信息
            header = f"# GameScout Prompt预览 - {range_desc}\n"
            header += f"# 选择平台: {platform_desc}\n"
            header += f"# 预览时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# 游戏数量: {len(prompts)}\n\n"
            header += "=" * 50 + "\n\n"
            text_area.insert(tk.END, header)

            # 显示prompts
            for i, prompt in enumerate(prompts, 1):
                text_area.insert(tk.END, f"{i}. {prompt}\n\n")

            text_area.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("错误", f"预览失败: {str(e)}")

    def export_prompts(self, recent_only=False):
        """导出prompts到txt文件"""
        try:
            # 根据选项获取游戏数据
            if recent_only:
                games = self.get_recent_unique_games()
                export_type = "recent"
                type_desc = "本次新增"
            else:
                games = self.get_unique_games()
                export_type = "all"
                type_desc = "全量"

            if not games:
                messagebox.showinfo("信息", f"暂无{type_desc}游戏数据")
                return

            # 生成prompts
            prompts = self.generate_prompts(games)

            # 使用游戏数量作为默认文件名
            default_filename = f"{len(prompts)}.txt"

            # 让用户选择保存路径
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                title=f"保存{type_desc}Prompts文件",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                initialfile=default_filename
            )

            if not filename:  # 用户取消了保存
                return

            # 写入文件
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# GameScout Prompt导出 - {type_desc}数据\n")
                f.write(f"# 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 游戏数量: {len(prompts)}\n")

                # 获取选中的平台信息
                selected_platforms = []
                for platform, var in self.platform_vars.items():
                    if var.get():
                        platform_display = platform.replace('.io', '').replace('.com', '').title()
                        selected_platforms.append(platform_display)

                if selected_platforms:
                    f.write(f"# 选择平台: {', '.join(selected_platforms)}\n")
                else:
                    f.write(f"# 选择平台: 所有平台\n")

                f.write("\n" + "=" * 50 + "\n\n")

                for i, prompt in enumerate(prompts, 1):
                    f.write(f"{i}. {prompt}\n\n")

            messagebox.showinfo("成功", f"{type_desc}Prompts已导出到:\n{filename}\n\n共导出 {len(prompts)} 个prompt")

        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")

    def get_unique_games(self):
        """获取选中平台的游戏数据并按name去重"""
        all_games = []

        # 获取用户选择的平台
        selected_platforms = []
        for platform, var in self.platform_vars.items():
            if var.get():  # 如果平台被选中
                selected_platforms.append(platform)

        # 如果没有选择任何平台，默认加载所有平台
        if not selected_platforms:
            selected_platforms = ['itch.io', 'azgames.io', 'armorgames.com', 'geoguessr.io']

        # 加载选中平台的数据
        for platform in selected_platforms:
            platform_games = self.data_manager.load_games(platform=platform)
            all_games.extend(platform_games)

        # 按name去重，保留第一个
        unique_games = []
        seen_names = set()

        for game in all_games:
            name = game.get('name', '').strip()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_games.append(game)

        return unique_games

    def get_recent_unique_games(self):
        """获取选中平台最近24小时的游戏数据并按name去重"""
        all_games = []

        # 获取用户选择的平台
        selected_platforms = []
        for platform, var in self.platform_vars.items():
            if var.get():  # 如果平台被选中
                selected_platforms.append(platform)

        # 如果没有选择任何平台，默认加载所有平台
        if not selected_platforms:
            selected_platforms = ['itch.io', 'azgames.io', 'armorgames.com', 'geoguessr.io']

        # 加载选中平台的最近数据
        for platform in selected_platforms:
            platform_games = self.data_manager.get_recent_games(platform=platform, hours=24)
            all_games.extend(platform_games)

        # 按name去重，保留第一个
        unique_games = []
        seen_names = set()

        for game in all_games:
            name = game.get('name', '').strip()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_games.append(game)

        return unique_games

    def generate_prompts(self, games):
        """根据游戏数据生成prompts"""
        prompts = []
        template = self.prompt_text.get('1.0', tk.END).strip()

        # 获取字段标签
        labels = {key: var.get() for key, var in self.field_labels.items()}

        for game in games:
            # 确定使用iframe_url还是embed_url
            iframe_url = game.get('iframe_url', '').strip()
            embed_url = game.get('embed_url', '').strip()

            if iframe_url:
                iframe_embed_url = self.clean_url_for_display(iframe_url)
                iframe_embed_label = labels['iframe_url']
            elif embed_url:
                iframe_embed_url = self.clean_url_for_display(embed_url)
                iframe_embed_label = labels['embed_url']
            else:
                continue  # 跳过没有有效链接的游戏

            # 替换模板中的占位符
            prompt = template.format(
                name=game.get('name', ''),
                name_label=labels['name'],
                url=game.get('url', ''),
                url_label=labels['url'],
                iframe_embed_url=iframe_embed_url,
                iframe_embed_label=iframe_embed_label
            )

            prompts.append(prompt)

        return prompts

    def get_manual_iframe(self):
        """手动获取游戏页面的iframe地址"""
        url = self.manual_url_var.get().strip()
        if not url:
            messagebox.showwarning("警告", "请输入游戏页面URL")
            return

        # 检查URL是否属于支持的平台
        supported_platforms = {
            'itch.io': 'itch.io',
            'azgames.io': 'azgames.io',
            'armorgames.com': 'armorgames.com',
            'geoguessr.io': 'geoguessr.io'
        }

        platform = None
        for domain, platform_name in supported_platforms.items():
            if domain in url:
                platform = platform_name
                break

        if not platform:
            messagebox.showerror("错误", "不支持的平台！\n支持的平台：Itch, AzGames, ArmorGames, GeoGuessr")
            return

        # 显示处理中状态
        self.manual_url_var.set("正在获取iframe地址...")
        self.root.update()

        try:
            embed_url = None
            game_name = "手动获取"

            # 根据平台使用相应的采集器获取embed URL
            if platform == 'itch.io':
                scraper = self.game_scraper
                # 对于itch.io，直接调用scrape_game_detail方法
                game_data = scraper.scrape_game_detail(url, game_name)
                if game_data:
                    embed_url = game_data.get('iframe_url') or game_data.get('embed_url')
            elif platform == 'azgames.io':
                scraper = AzGamesScraper()
                # 对于azgames.io，调用scrape_game_detail方法
                game_data = scraper.scrape_game_detail(url, game_name)
                if game_data:
                    embed_url = game_data.get('embed_url')
            elif platform == 'armorgames.com':
                scraper = ArmorGamesScraper()
                # 对于armorgames.com，调用scrape_game_detail方法
                game_data = scraper.scrape_game_detail(url, game_name)
                if game_data:
                    embed_url = game_data.get('embed_url')
            elif platform == 'geoguessr.io':
                scraper = GeoGuessrScraper()
                # 对于geoguessr.io，调用scrape_game_detail方法
                game_data = scraper.scrape_game_detail(url, game_name)
                if game_data:
                    embed_url = game_data.get('embed_url')

            # 恢复输入框
            self.manual_url_var.set(url)

            if embed_url:
                # 显示结果对话框
                result_window = tk.Toplevel(self.root)
                result_window.title("获取结果")
                result_window.geometry("650x350")
                result_window.resizable(True, True)

                # 设置窗口图标
                try:
                    result_window.iconbitmap("logo.ico")
                except:
                    pass  # 如果图标文件不存在，忽略错误

                # 设置窗口居中
                result_window.transient(self.root)
                result_window.grab_set()

                # 创建主框架
                main_frame = ttk.Frame(result_window, padding="10")
                main_frame.pack(fill=tk.BOTH, expand=True)

                # FAQ参考链接：原始URL
                ttk.Label(main_frame, text="FAQ参考链接：", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
                url_text = tk.Text(main_frame, height=2, wrap=tk.WORD)
                url_text.pack(fill=tk.X, pady=(0, 10))
                url_text.insert(tk.END, url)
                url_text.config(state=tk.DISABLED)

                # IFRAME引入地址：
                ttk.Label(main_frame, text="IFRAME引入地址：", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
                iframe_text = tk.Text(main_frame, height=2, wrap=tk.WORD)
                iframe_text.pack(fill=tk.X, pady=(0, 10))
                iframe_text.insert(tk.END, embed_url)
                iframe_text.config(state=tk.DISABLED)

                # 按钮框架
                button_frame = ttk.Frame(main_frame)
                button_frame.pack(fill=tk.X, pady=(10, 0))

                # 复制格式化内容按钮
                def copy_formatted():
                    # 清理embed_url，使用与game_scraper相同的逻辑
                    clean_embed_url = self.clean_url_for_display(embed_url)

                    formatted_content = f"FAQ参考：{url}\nIFRAME引入地址：{clean_embed_url}"
                    self.root.clipboard_clear()
                    self.root.clipboard_append(formatted_content)
                    messagebox.showinfo("成功", "内容已复制到剪贴板")

                ttk.Button(button_frame, text="复制",
                          command=copy_formatted).pack(side=tk.LEFT, padx=(0, 5))

                # 关闭按钮
                ttk.Button(button_frame, text="关闭",
                          command=result_window.destroy).pack(side=tk.RIGHT)

                # 平台信息
                platform_display = platform.replace('.io', '').replace('.com', '').title()
                ttk.Label(main_frame, text=f"平台: {platform_display}",
                         foreground="gray").pack(anchor=tk.W, pady=(10, 0))

            else:
                messagebox.showerror("错误", f"无法从该页面获取iframe地址\n\n可能的原因：\n1. 页面不存在或无法访问\n2. 页面结构不符合预期\n3. 网络连接问题")

        except Exception as e:
            # 恢复输入框
            self.manual_url_var.set(url)
            messagebox.showerror("错误", f"获取iframe地址时发生错误：\n{str(e)}")

    def clean_url_for_display(self, url):
        """
        清理URL用于显示，去除重复的/index.html和?v=参数
        与game_scraper.py中的clean_iframe_url逻辑保持一致
        """
        if not url:
            return url

        clean_url = url

        # 清理itch.zone URL中的?v=参数和重复的/index.html
        if 'itch.zone' in clean_url:
            # 移除?v=参数
            if '?v=' in clean_url:
                clean_url = clean_url.split('?v=')[0]

            # 更全面的重复/index.html检测和修复
            # 1. 检测并修复 /index.html/index.html 结尾的情况
            if clean_url.endswith('/index.html/index.html'):
                clean_url = clean_url.replace('/index.html/index.html', '/index.html')

            # 2. 检测并修复中间出现重复的情况，如 /index.html/index.html/
            elif '/index.html/index.html/' in clean_url:
                clean_url = clean_url.replace('/index.html/index.html/', '/index.html/')

            # 3. 检测并修复多重重复的情况
            while '/index.html/index.html' in clean_url:
                clean_url = clean_url.replace('/index.html/index.html', '/index.html')

        return clean_url

    def open_website(self, event):
        """打开prompt2tool.com网站"""
        import webbrowser
        webbrowser.open("https://prompt2tool.com")

def main():
    """主函数"""
    root = tk.Tk()
    app = GameScoutApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
