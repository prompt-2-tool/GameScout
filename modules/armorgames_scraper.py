"""
ArmorGames.com 游戏采集器
"""

import time
import random
import re
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import requests
from bs4 import BeautifulSoup


class ArmorGamesScraper:
    def __init__(self, max_games_limit=50):
        """
        初始化ArmorGames采集器
        
        Args:
            max_games_limit (int): 最大采集游戏数量限制
        """
        self.max_games_limit = max_games_limit
        self.should_stop = False
        self.driver = None
        self.logger = logging.getLogger(__name__)
        
        # 使用固定的User-Agent
        self.fixed_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        # 初始化requests session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.fixed_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def init_driver(self):
        """初始化Chrome WebDriver"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 设置固定User-Agent
            chrome_options.add_argument(f'--user-agent={self.fixed_user_agent}')

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            self.logger.info(f"WebDriver 初始化成功，使用固定UA: {self.fixed_user_agent}")
            return True
            
        except Exception as e:
            self.logger.error(f"WebDriver 初始化失败: {str(e)}")
            return False

    def random_delay(self, min_seconds=2, max_seconds=8):
        """随机延时"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def stop_scraping(self):
        """停止采集"""
        self.should_stop = True
        self.cleanup_driver()

    def cleanup_driver(self):
        """清理WebDriver资源"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("ArmorGames WebDriver已正常关闭")
            except Exception as e:
                self.logger.warning(f"ArmorGames WebDriver关闭时出现异常: {str(e)}")
            finally:
                self.driver = None

    def __del__(self):
        """析构函数，确保资源清理"""
        self.cleanup_driver()

    def scrape_games(self, progress_callback=None, stop_flag=None):
        """
        采集ArmorGames.com游戏数据

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
                progress_callback("正在获取ArmorGames游戏列表...")

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

            # 第三步：逐个采集游戏详情
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
                            progress_callback(f"跳过游戏: {game_name} (无有效embed URL)")

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

    def get_all_games_list(self, progress_callback=None, stop_flag=None):
        """
        获取所有游戏的基本信息列表（名称和URL），并过滤已存在的游戏

        Args:
            progress_callback: 进度回调函数
            stop_flag: 停止标志函数

        Returns:
            list: [(game_name, game_url), ...] 游戏信息元组列表（已过滤重复）
        """
        game_list = []

        try:
            if progress_callback:
                progress_callback("正在获取已存在的游戏列表进行去重...")

            # 获取已存在的游戏名称（跨平台去重）
            from .data_manager import DataManager
            data_manager = DataManager()
            existing_games = data_manager.load_games()  # 加载所有平台的游戏
            existing_names = {data_manager.normalize_game_name(game.get('name', ''))
                            for game in existing_games}

            if progress_callback:
                progress_callback(f"数据库中已有 {len(existing_names)} 个游戏，开始获取ArmorGames游戏列表...")

            url = "https://armorgames.com/games/date#games"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 查找游戏列表元素 - 根据要求查找 <ul class="gamelisting"> 中的 li 标签
            game_listing = soup.find('ul', class_='gamelisting')
            if not game_listing:
                if progress_callback:
                    progress_callback("未找到游戏列表容器")
                return game_list

            game_items = game_listing.find_all('li')

            if progress_callback:
                progress_callback(f"在页面中找到 {len(game_items)} 个游戏项目，开始过滤重复...")

            processed_urls = set()
            skipped_count = 0

            for item in game_items:
                if stop_flag and stop_flag():
                    break

                try:
                    # 在li标签中查找游戏链接
                    link_element = item.find('a')
                    if not link_element:
                        continue

                    # 获取游戏链接
                    game_url = link_element.get('href')
                    if not game_url:
                        continue

                    # 如果是相对路径，拼接主域名
                    if game_url.startswith('/'):
                        game_url = 'https://armorgames.com' + game_url

                    # 避免重复
                    if game_url in processed_urls:
                        continue

                    # 获取游戏名称 - 从链接的title属性或文本内容获取
                    game_name = link_element.get('title')
                    if not game_name:
                        # 尝试从链接文本获取
                        game_name = link_element.get_text(strip=True)
                    
                    # 如果还没有名称，尝试从图片的alt属性获取
                    if not game_name:
                        img_element = link_element.find('img')
                        if img_element:
                            game_name = img_element.get('alt') or img_element.get('title')

                    # 清理游戏名称，去除前后空格
                    if game_name:
                        game_name = game_name.strip()

                    # 验证游戏信息有效性
                    if game_name and self.is_valid_game_entry(game_name, game_url):
                        # 检查是否已存在（跨平台去重）
                        normalized_name = data_manager.normalize_game_name(game_name)
                        if normalized_name in existing_names:
                            skipped_count += 1
                            self.logger.debug(f"跳过已存在游戏: {game_name}")
                            continue

                        game_list.append((game_name, game_url))
                        processed_urls.add(game_url)
                        existing_names.add(normalized_name)  # 添加到已存在列表，避免本次内部重复

                        if progress_callback and len(game_list) % 10 == 0:
                            progress_callback(f"已收集 {len(game_list)} 个新游戏，跳过 {skipped_count} 个重复...")

                except Exception as e:
                    self.logger.error(f"处理游戏项目时出错: {str(e)}")
                    continue

            if progress_callback:
                progress_callback(f"ArmorGames游戏列表获取完成，共 {len(game_list)} 个新游戏，跳过 {skipped_count} 个重复")

        except Exception as e:
            self.logger.error(f"获取游戏列表失败: {str(e)}")
            if progress_callback:
                progress_callback(f"获取游戏列表失败: {str(e)}")

        return game_list

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
        if not game_name or len(game_name) < 2:
            return False

        # 检查URL是否指向真正的游戏页面
        if not game_url or 'armorgames.com' not in game_url:
            return False

        # 过滤掉分类页面和其他非游戏页面
        invalid_patterns = [
            '/category/',
            '/tag/',
            '/search',
            '/user/',
            '/about',
            '/contact',
            '/privacy',
            '/terms',
            '/#',
            'javascript:',
            'mailto:',
            'tel:',
            '/upload/',
            '/static/',
            '/css/',
            '/js/',
            '/images/',
            '/games/date'  # 排除列表页面本身
        ]

        for pattern in invalid_patterns:
            if pattern in game_url.lower():
                self.logger.debug(f"过滤掉非游戏链接: {game_url}")
                return False

        # 确保是具体的游戏页面（通常是 /game-name/id 格式）
        if not re.search(r'/[^/]+-game/\d+', game_url):
            self.logger.debug(f"过滤掉非游戏页面: {game_url}")
            return False

        return True

    def scrape_game_detail(self, game_url, game_name):
        """
        采集单个游戏的详细信息

        Args:
            game_url (str): 游戏页面URL
            game_name (str): 游戏名称

        Returns:
            dict: 游戏数据字典
        """
        try:
            self.logger.info(f"正在处理游戏: {game_name} - {game_url}")

            # 使用requests获取游戏详情页面
            response = self.session.get(game_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 提取embed URL
            embed_url = self.extract_embed_url(soup, game_url, response.text)

            # 只有当embed_url有效时才返回数据
            if embed_url and embed_url.strip():
                game_data = {
                    'name': game_name,
                    'url': game_url,
                    'embed_url': embed_url,
                    'iframe_url': "",  # armorgames使用embed_url，这里保持空
                    'platform': 'armorgames.com',
                    'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                self.logger.info(f"成功采集游戏: {game_name} -> {embed_url}")
                return game_data
            else:
                self.logger.warning(f"游戏 {game_name} 没有有效的embed URL，跳过")
                return None

        except Exception as e:
            self.logger.error(f"采集游戏详情失败 {game_url}: {str(e)}")
            return None

    def extract_embed_url(self, soup, game_url, html_content=None):
        """
        从游戏详情页面提取embed URL
        根据要求，查找 <iframe id="html-game-frame"> 中的 data-src 属性
        并去掉 ?v= 参数

        Args:
            soup: BeautifulSoup对象
            game_url (str): 游戏页面URL
            html_content (str): 原始HTML内容

        Returns:
            str: embed URL
        """
        try:
            # 方法1: 查找指定的iframe元素
            iframe = soup.find('iframe', id='html-game-frame')
            if iframe:
                data_src = iframe.get('data-src')
                if data_src:
                    # 去掉 ?v= 参数
                    clean_url = self.clean_embed_url(data_src)
                    self.logger.info(f"通过iframe#html-game-frame找到URL: {clean_url}")
                    return clean_url

            # 方法2: 查找所有包含armorgames.com的iframe
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                data_src = iframe.get('data-src') or iframe.get('src')
                if data_src and 'armorgames.com' in data_src:
                    clean_url = self.clean_embed_url(data_src)
                    self.logger.info(f"通过iframe元素找到URL: {clean_url}")
                    return clean_url

            # 方法3: 在整个HTML中搜索包含cache.armorgames.com的URL
            if html_content:
                # 搜索所有可能的embed URL模式
                embed_patterns = [
                    r'data-src=[\'\"](https://[^\'\"]*\.cache\.armorgames\.com[^\'\"]*)[\'\"]*',
                    r'src=[\'\"](https://[^\'\"]*\.cache\.armorgames\.com[^\'\"]*)[\'\"]*',
                    r'(https://\d+\.cache\.armorgames\.com/files/games/[^\'\"\\s]+)',
                ]

                for pattern in embed_patterns:
                    matches = re.findall(pattern, html_content)
                    if matches:
                        clean_url = self.clean_embed_url(matches[0])
                        self.logger.info(f"通过HTML搜索找到URL: {clean_url}")
                        return clean_url

            return None

        except Exception as e:
            self.logger.error(f"提取embed URL时出错: {str(e)}")
            return None

    def clean_embed_url(self, url):
        """
        清理embed URL，去掉?v=参数

        Args:
            url (str): 原始URL

        Returns:
            str: 清理后的URL
        """
        if not url:
            return url

        # 去掉 ?v= 参数
        if '?v=' in url:
            url = url.split('?v=')[0]

        return url
