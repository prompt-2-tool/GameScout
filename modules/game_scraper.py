#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
游戏采集模块
用于采集itch.io网站的游戏数据
"""

import requests
import time
import re
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


class GameScraper:
    """游戏采集器"""
    
    def __init__(self, max_games_limit=50):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()

        # 使用固定的搜索引擎UA，避免频繁变化
        self.fixed_user_agent = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'

        self.session.headers.update({
            'User-Agent': self.fixed_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        self.driver = None
        self.should_stop = False
        self.max_games_limit = max_games_limit  # 采集数量限制
        self.logger.info(f"使用固定搜索引擎UA: {self.fixed_user_agent}")

    def random_delay(self, min_seconds=1, max_seconds=3):
        """随机延时，模拟真人行为"""
        import random
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def simulate_human_behavior(self):
        """模拟真人浏览行为"""
        try:
            if self.driver:
                # 随机滚动
                import random
                scroll_height = random.randint(200, 800)
                self.driver.execute_script(f"window.scrollBy(0, {scroll_height});")
                self.random_delay(0.5, 1.5)

                # 随机移动鼠标（通过JavaScript模拟）
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                self.driver.execute_script(f"""
                    var event = new MouseEvent('mousemove', {{
                        'view': window,
                        'bubbles': true,
                        'cancelable': true,
                        'clientX': {x},
                        'clientY': {y}
                    }});
                    document.dispatchEvent(event);
                """)

        except Exception as e:
            self.logger.debug(f"模拟人类行为时出错: {str(e)}")

    def rotate_user_agent(self):
        """保持固定User-Agent，不再轮换"""
        # 为了保持兼容性，保留此方法但不执行任何操作
        self.logger.debug("使用固定UA策略，不进行轮换")
        
    def setup_driver(self):
        """设置Selenium WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')

            # 临时文件和缓存管理 - 减少临时文件产生
            chrome_options.add_argument('--disable-background-timer-throttling')
            chrome_options.add_argument('--disable-backgrounding-occluded-windows')
            chrome_options.add_argument('--disable-renderer-backgrounding')
            chrome_options.add_argument('--disable-features=TranslateUI')
            chrome_options.add_argument('--disable-ipc-flooding-protection')
            chrome_options.add_argument('--no-default-browser-check')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--disable-logging')
            chrome_options.add_argument('--disable-gpu-logging')
            chrome_options.add_argument('--silent')
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-sync')

            # 设置临时目录到项目目录而不是系统临时目录
            temp_dir = os.path.join(os.getcwd(), 'temp_chrome')
            os.makedirs(temp_dir, exist_ok=True)
            chrome_options.add_argument(f'--user-data-dir={temp_dir}')
            chrome_options.add_argument(f'--data-path={temp_dir}')
            chrome_options.add_argument(f'--disk-cache-dir={temp_dir}')

            # 使用固定的搜索引擎UA
            chrome_options.add_argument(f'--user-agent={self.fixed_user_agent}')

            # 反检测设置
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins-discovery')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # 执行脚本来隐藏webdriver属性和模拟真实浏览器
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.chrome = {runtime: {}};
                Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})});
            """)

            self.logger.info(f"WebDriver 初始化成功，使用固定UA: {self.fixed_user_agent}")
            return True
        except Exception as e:
            self.logger.error(f"WebDriver 初始化失败: {str(e)}")
            return False
            
    def stop(self):
        """停止采集"""
        self.should_stop = True
        self.cleanup_driver()

    def cleanup_driver(self):
        """清理WebDriver资源"""
        if self.driver:
            try:
                # 尝试关闭所有窗口
                self.driver.quit()
                self.logger.info("WebDriver已正常关闭")
            except Exception as e:
                self.logger.warning(f"WebDriver关闭时出现异常: {str(e)}")
                try:
                    # 强制终止进程
                    import psutil
                    import os
                    current_pid = os.getpid()
                    for proc in psutil.process_iter(['pid', 'name']):
                        if 'chrome' in proc.info['name'].lower() and proc.info['pid'] != current_pid:
                            try:
                                proc.terminate()
                            except:
                                pass
                except ImportError:
                    # 如果没有psutil，使用基本清理
                    pass
            finally:
                self.driver = None

    def __del__(self):
        """析构函数，确保资源清理"""
        self.cleanup_driver()
                
    def scrape_games(self, progress_callback=None, stop_flag=None):
        """
        采集itch.io游戏数据 - 新策略：先获取所有游戏列表，再逐个采集

        Args:
            progress_callback: 进度回调函数
            stop_flag: 停止标志函数

        Returns:
            list: 游戏数据列表
        """
        games = []

        try:
            # 第一步：获取所有游戏的基本信息（名称和URL）
            if progress_callback:
                progress_callback("正在获取itch.io游戏列表...")

            game_list = self.get_all_games_list(progress_callback, stop_flag)

            if not game_list:
                if progress_callback:
                    progress_callback("未能获取到游戏列表")
                return games

            if progress_callback:
                progress_callback(f"获取到 {len(game_list)} 个游戏，开始逐个采集详情...")

            # 第二步：根据用户设置的数量限制，逐个采集游戏详情
            max_games = getattr(self, 'test_limit', None) or self.max_games_limit
            if max_games and max_games > 0:
                game_list = game_list[:max_games]
                if progress_callback:
                    progress_callback(f"根据设置限制，将采集前 {len(game_list)} 个游戏")

            # 第三步：逐个采集游戏详情（不再变化UA，使用固定的搜索引擎UA）
            for i, (game_name, game_url) in enumerate(game_list, 1):
                if stop_flag and stop_flag() or self.should_stop:
                    break

                if progress_callback:
                    progress_callback(f"正在采集游戏 {i}/{len(game_list)}: {game_name}")

                try:
                    game_data = self.scrape_game_detail(game_url, game_name)
                    if game_data:
                        games.append(game_data)
                        if progress_callback:
                            progress_callback(f"成功采集游戏: {game_name}", len(games))
                    else:
                        if progress_callback:
                            progress_callback(f"跳过游戏: {game_name} (无有效iframe URL)")

                    # 适当延时，避免请求过于频繁
                    self.random_delay(1, 3)

                except Exception as e:
                    self.logger.error(f"采集游戏详情失败 {game_name}: {str(e)}")
                    if progress_callback:
                        progress_callback(f"采集失败: {game_name} - {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"采集过程中发生错误: {str(e)}")
            if progress_callback:
                progress_callback(f"采集错误: {str(e)}")

        return games

    def scrape_with_requests(self, progress_callback=None, stop_flag=None):
        """
        使用requests作为备用方案采集游戏数据

        Args:
            progress_callback: 进度回调函数
            stop_flag: 停止标志函数

        Returns:
            list: 游戏数据列表
        """
        games = []

        try:
            if progress_callback:
                progress_callback("使用requests方案采集数据...")

            url = "https://itch.io/games/new-and-popular/featured/free/platform-web"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 查找游戏链接，使用更精确的选择器
            game_links = soup.find_all('a', {'class': 'title game_link', 'data-action': 'game_grid'})

            if not game_links:
                # 尝试其他选择器
                game_links = soup.find_all('a', class_='game_link')
                # 进一步过滤，只保留包含title类的
                game_links = [link for link in game_links if 'title' in link.get('class', [])]

            if progress_callback:
                progress_callback(f"找到 {len(game_links)} 个游戏链接")

            for i, link in enumerate(game_links):
                if stop_flag and stop_flag():
                    break

                try:
                    game_url = link.get('href')
                    game_name = self.extract_game_name(link)

                    if (game_url and game_name and
                        self.is_valid_game_entry(game_name, game_url)):
                        # 确保URL是完整的
                        if game_url.startswith('/'):
                            game_url = 'https://itch.io' + game_url

                        if progress_callback:
                            progress_callback(f"正在处理游戏 {i+1}/{len(game_links)}: {game_name}")

                        # 获取游戏详情
                        game_data = self.scrape_game_detail(game_url, game_name)
                        if game_data:
                            games.append(game_data)

                            if progress_callback:
                                progress_callback(f"成功采集游戏: {game_name}", len(games))

                        # 随机延时，模拟真人浏览
                        self.random_delay(3, 8)

                        # 限制采集数量
                        max_games = getattr(self, 'test_limit', None) or self.max_games_limit
                        if max_games and len(games) >= max_games:
                            if progress_callback:
                                progress_callback(f"已达到采集数量限制 ({max_games})")
                            break

                except Exception as e:
                    self.logger.error(f"处理游戏链接时出错: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"requests方案采集失败: {str(e)}")
            if progress_callback:
                progress_callback(f"requests方案失败: {str(e)}")

        return games

    def get_all_games_list(self, progress_callback=None, stop_flag=None):
        """
        获取所有itch.io游戏的基本信息列表（名称和URL）

        Args:
            progress_callback: 进度回调函数
            stop_flag: 停止标志函数

        Returns:
            list: [(game_name, game_url), ...] 游戏信息元组列表
        """
        game_list = []

        try:
            if progress_callback:
                progress_callback("使用requests方案获取itch.io游戏列表...")

            url = "https://itch.io/games/new-and-popular/featured/free/platform-web"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 查找游戏链接元素
            game_links = soup.select('a.title.game_link[data-action="game_grid"]')

            if progress_callback:
                progress_callback(f"在页面中找到 {len(game_links)} 个游戏链接")

            processed_urls = set()

            for link in game_links:
                if stop_flag and stop_flag():
                    break

                try:
                    # 获取游戏链接
                    game_url = link.get('href')
                    if not game_url:
                        continue

                    # 如果是相对路径，拼接主域名
                    if game_url.startswith('/'):
                        game_url = 'https://itch.io' + game_url

                    # 避免重复
                    if game_url in processed_urls:
                        continue

                    # 获取游戏名称
                    game_name = link.get_text(strip=True)

                    # 验证游戏信息有效性
                    if game_name and self.is_valid_game_entry(game_name, game_url):
                        game_list.append((game_name, game_url))
                        processed_urls.add(game_url)

                        if progress_callback and len(game_list) % 10 == 0:
                            progress_callback(f"已收集 {len(game_list)} 个游戏信息...")

                except Exception as e:
                    self.logger.error(f"处理游戏链接时出错: {str(e)}")
                    continue

            if progress_callback:
                progress_callback(f"itch.io游戏列表获取完成，共 {len(game_list)} 个有效游戏")

        except Exception as e:
            self.logger.error(f"获取itch.io游戏列表失败: {str(e)}")
            if progress_callback:
                progress_callback(f"获取游戏列表失败: {str(e)}")

        return game_list

    def load_more_games(self):
        """加载更多游戏"""
        try:
            # 滚动到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # 查找并点击"加载更多"按钮或等待自动加载
            try:
                # 等待新内容加载
                initial_count = len(self.driver.find_elements(By.CSS_SELECTOR, "a.game_link[data-action='game_grid']"))
                time.sleep(3)
                final_count = len(self.driver.find_elements(By.CSS_SELECTOR, "a.game_link[data-action='game_grid']"))
                
                return final_count > initial_count
            except:
                return False
                
        except Exception as e:
            self.logger.error(f"加载更多游戏时出错: {str(e)}")
            return False
            
    def scrape_game_detail(self, game_url, game_name):
        """
        采集游戏详情页面
        
        Args:
            game_url (str): 游戏页面URL
            game_name (str): 游戏名称
            
        Returns:
            dict: 游戏数据
        """
        try:
            response = self.session.get(game_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 查找iframe游戏地址
            iframe_url = self.extract_iframe_url(soup, response.text)
            
            # 只有当iframe_url有效时才返回数据
            if iframe_url and iframe_url.strip():
                game_data = {
                    'name': game_name,
                    'url': game_url,
                    'embed_url': "",  # itch.io使用iframe_url，这里保持空
                    'iframe_url': iframe_url,
                    'platform': 'itch.io',
                    'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                self.logger.info(f"成功采集游戏: {game_name}")
                return game_data
            else:
                self.logger.warning(f"游戏 {game_name} 没有有效的iframe URL，跳过")
                return None
            
        except Exception as e:
            self.logger.error(f"采集游戏详情失败 {game_url}: {str(e)}")
            return None
            
    def extract_iframe_url(self, soup, html_content):
        """
        从游戏页面提取iframe URL

        Args:
            soup: BeautifulSoup对象
            html_content: 原始HTML内容

        Returns:
            str: iframe URL
        """
        iframe_url = None

        try:
            # 方法1: 查找iframe标签
            iframe = soup.find('iframe')
            if iframe and iframe.get('src'):
                raw_url = iframe.get('src')
                iframe_url = self.clean_iframe_url(raw_url)
                if iframe_url:
                    self.logger.info(f"通过iframe标签找到URL: {iframe_url}")

            # 方法2: 使用精确的正则表达式匹配itch.zone游戏URL
            if not iframe_url:
                # 专门匹配 https://html-classic.itch.zone/html/{数字}/{游戏名}/index.html 格式
                # 游戏名可能包含字母、数字、连字符、下划线等
                itch_zone_pattern = r'https://html-classic\.itch\.zone/html/\d+/[^/\s"\'&]+/index\.html'

                # 在HTML内容中查找所有匹配的URL
                matches = re.findall(itch_zone_pattern, html_content, re.IGNORECASE)

                if matches:
                    # 取第一个匹配的URL
                    iframe_url = matches[0]
                    self.logger.info(f"通过精确正则表达式找到itch.zone URL: {iframe_url}")
                else:
                    # 如果精确匹配失败，尝试更宽松的模式
                    fallback_patterns = [
                        # 匹配任何itch.zone域名的URL
                        r'https://[^"\'&\s]*\.itch\.zone/[^"\'&\s]*',
                        # 匹配被HTML转义的URL
                        r'&quot;(https://[^&]*\.itch\.zone/[^&]*)&quot;',
                        # 匹配JSON字段中的URL
                        r'"(?:play_url|embed_url|game_url)"\s*:\s*"([^"]*itch\.zone[^"]*)"',
                        # 匹配src属性
                        r'src\s*=\s*["\']([^"\']*itch\.zone[^"\']*)["\']',
                    ]

                    for pattern in fallback_patterns:
                        matches = re.findall(pattern, html_content, re.IGNORECASE)
                        if matches:
                            # 清理和验证每个匹配的URL
                            for match in matches:
                                cleaned_url = self.clean_iframe_url(match)
                                if cleaned_url and 'html-classic.itch.zone' in cleaned_url:
                                    iframe_url = cleaned_url
                                    self.logger.info(f"通过备用正则表达式找到URL: {iframe_url}")
                                    break
                            if iframe_url:
                                break

            # 方法3: 查找embed相关的URL
            if not iframe_url:
                embed_patterns = [
                    r'embed_url["\']?\s*:\s*["\']([^"\']*)["\']',
                    r'"embed_url"\s*:\s*"([^"]*)"',
                    r'embedUrl["\']?\s*:\s*["\']([^"\']*)["\']',
                    r'game_embed_url["\']?\s*:\s*["\']([^"\']*)["\']'
                ]

                for pattern in embed_patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    if matches:
                        iframe_url = matches[0]
                        self.logger.info(f"通过embed模式找到URL: {iframe_url}")
                        break

            # 方法4: 查找游戏容器中的数据属性
            if not iframe_url:
                game_frame = soup.find('div', class_='game_frame')
                if game_frame:
                    # 查找data属性
                    for attr in game_frame.attrs:
                        if 'url' in attr.lower() and game_frame.attrs[attr]:
                            url_value = game_frame.attrs[attr]
                            if 'itch.zone' in url_value:
                                iframe_url = url_value
                                self.logger.info(f"通过data属性找到URL: {iframe_url}")
                                break

            # 使用专门的清理函数
            if iframe_url:
                iframe_url = self.clean_iframe_url(iframe_url)

        except Exception as e:
            self.logger.error(f"提取iframe URL时出错: {str(e)}")

        return iframe_url

    def clean_iframe_url(self, raw_url):
        """
        清理和验证iframe URL，专门处理itch.zone游戏URL

        Args:
            raw_url (str): 原始URL

        Returns:
            str: 清理后的URL，如果无效则返回None
        """
        if not raw_url:
            return None

        try:
            # 移除HTML转义字符
            url = raw_url.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            url = url.replace('\\/', '/').replace('\\"', '"').replace('\\', '')

            # 移除前后的引号和空白字符
            url = url.strip().strip('"\'')

            # 清理itch.zone URL中的?v=参数和重复的/index.html
            if 'itch.zone' in url:
                # 移除?v=参数
                if '?v=' in url:
                    url = url.split('?v=')[0]
                    self.logger.info(f"移除?v=参数后的URL: {url}")

                # 更全面的重复/index.html检测和修复
                # 1. 检测并修复 /index.html/index.html 结尾的情况
                if url.endswith('/index.html/index.html'):
                    url = url.replace('/index.html/index.html', '/index.html')
                    self.logger.info(f"修复重复index.html后的URL: {url}")

                # 2. 检测并修复中间出现重复的情况，如 /index.html/index.html/
                elif '/index.html/index.html/' in url:
                    url = url.replace('/index.html/index.html/', '/index.html/')
                    self.logger.info(f"修复中间重复index.html后的URL: {url}")

                # 3. 检测并修复多重重复的情况
                while '/index.html/index.html' in url:
                    url = url.replace('/index.html/index.html', '/index.html')
                    self.logger.info(f"修复多重重复index.html后的URL: {url}")

            # 验证是否为itch.zone域名
            if 'itch.zone' not in url:
                return None

            # 排除非游戏URL
            exclude_keywords = ['youtube', 'twitter', 'facebook', 'instagram', 'discord', 'github']
            if any(keyword in url.lower() for keyword in exclude_keywords):
                return None

            # 确保URL格式正确
            if not url.startswith('http'):
                if url.startswith('//'):
                    url = 'https:' + url
                else:
                    url = 'https://' + url

            # 验证是否符合标准的itch.zone游戏URL格式
            # 支持两种格式:
            # 1. https://html-classic.itch.zone/html/{数字}/{游戏名}/index.html
            # 2. https://html-classic.itch.zone/html/{数字}/index.html (直接在ID目录下)
            itch_zone_patterns = [
                r'^https://html-classic\.itch\.zone/html/\d+/[^/\s"\'&]+/index\.html$',  # 标准格式
                r'^https://html-classic\.itch\.zone/html/\d+/index\.html$'  # 直接格式
            ]

            for pattern in itch_zone_patterns:
                if re.match(pattern, url, re.IGNORECASE):
                    self.logger.info(f"验证通过的itch.zone URL: {url}")
                    return url

            if 'html-classic.itch.zone' in url:
                # 如果包含html-classic.itch.zone但格式不标准，尝试修复
                # 提取数字ID和游戏名/路径
                match = re.search(r'html-classic\.itch\.zone/html/(\d+)/(.+)', url, re.IGNORECASE)
                if match:
                    game_id = match.group(1)
                    path_part = match.group(2)

                    # 特殊情况1: 如果路径部分就是 "index.html"，说明这是直接在ID目录下的游戏
                    if path_part == 'index.html':
                        fixed_url = f"https://html-classic.itch.zone/html/{game_id}/index.html"
                        self.logger.info(f"修复直接index.html格式的URL: {fixed_url}")
                        return fixed_url

                    # 特殊情况2: 如果路径部分是 "index.html/index.html"，去除重复
                    elif path_part == 'index.html/index.html':
                        fixed_url = f"https://html-classic.itch.zone/html/{game_id}/index.html"
                        self.logger.info(f"修复重复index.html的URL: {fixed_url}")
                        return fixed_url

                    # 特殊情况3: 如果路径部分以 "/index.html/index.html" 结尾，去除重复
                    elif path_part.endswith('/index.html/index.html'):
                        # 提取游戏名部分（去除重复的/index.html/index.html）
                        game_name = path_part.replace('/index.html/index.html', '')
                        fixed_url = f"https://html-classic.itch.zone/html/{game_id}/{game_name}/index.html"
                        self.logger.info(f"修复路径中重复index.html的URL: {fixed_url}")
                        return fixed_url

                    # 正常情况: 如果路径部分不以index.html结尾，添加index.html
                    elif not path_part.endswith('/index.html'):
                        # 确保路径部分不是单独的index.html（避免重复）
                        if path_part != 'index.html':
                            fixed_url = f"https://html-classic.itch.zone/html/{game_id}/{path_part}/index.html"
                        else:
                            fixed_url = f"https://html-classic.itch.zone/html/{game_id}/index.html"
                        self.logger.info(f"修复后的itch.zone URL: {fixed_url}")
                        return fixed_url

                    # 如果路径部分已经正确以/index.html结尾，直接返回
                    else:
                        fixed_url = f"https://html-classic.itch.zone/html/{game_id}/{path_part}"
                        self.logger.info(f"URL格式已正确: {fixed_url}")
                        return fixed_url

            # 如果是其他itch.zone域名，也接受
            elif '.itch.zone' in url:
                # 验证URL格式
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                if parsed.netloc and parsed.scheme:
                    self.logger.info(f"其他itch.zone域名URL: {url}")
                    return url

            return None

        except Exception as e:
            self.logger.error(f"清理iframe URL时出错: {str(e)}")
            return None



    def is_valid_game_entry(self, game_name, game_url):
        """
        验证游戏条目是否有效

        Args:
            game_name (str): 游戏名称
            game_url (str): 游戏URL

        Returns:
            bool: 是否为有效的游戏条目
        """
        # 过滤掉无效的游戏名称
        invalid_names = [
            'gif', 'video', 'trailer', 'preview', 'demo video',
            'gameplay', 'screenshot', 'image', 'pic', 'photo'
        ]

        # 检查游戏名称是否过短或包含无效关键词
        if len(game_name) < 2:
            return False

        if game_name.lower() in invalid_names:
            self.logger.info(f"过滤掉无效游戏名称: {game_name}")
            return False

        # 检查URL是否指向真正的游戏页面
        if not game_url or 'itch.io' not in game_url:
            return False

        # 过滤掉明显不是游戏的URL
        invalid_url_patterns = [
            '/jam/', '/community/', '/blog/', '/devlog/',
            '/profile/', '/collection/', '/bundle/'
        ]

        for pattern in invalid_url_patterns:
            if pattern in game_url.lower():
                self.logger.info(f"过滤掉无效游戏URL: {game_url}")
                return False

        return True

    def extract_game_name(self, link_element):
        """
        从链接元素中提取游戏名称

        Args:
            link_element: Selenium WebElement或BeautifulSoup Tag

        Returns:
            str: 游戏名称
        """
        try:
            # 如果是Selenium WebElement
            if hasattr(link_element, 'get_attribute'):
                # 首先尝试获取data-label属性中的游戏名称
                data_label = link_element.get_attribute('data-label')
                if data_label and 'title' in data_label:
                    # data-label格式通常是 "game:ID:title"
                    parts = data_label.split(':')
                    if len(parts) >= 3 and parts[2] == 'title':
                        # 获取链接的文本内容
                        text = link_element.text.strip()
                        if text and len(text) > 1:
                            return text

                # 如果没有data-label，直接获取文本
                text = link_element.text.strip()

                # 过滤掉明显不是游戏名称的文本
                if text and text.lower() not in ['gif', 'video', 'image', 'pic']:
                    return text

            # 如果是BeautifulSoup Tag
            elif hasattr(link_element, 'get_text'):
                text = link_element.get_text(strip=True)
                if text and text.lower() not in ['gif', 'video', 'image', 'pic']:
                    return text

        except Exception as e:
            self.logger.error(f"提取游戏名称时出错: {str(e)}")

        return ""
