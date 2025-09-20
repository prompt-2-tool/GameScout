"""
AzGames.io 游戏采集器
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


class AzGamesScraper:
    def __init__(self, max_games_limit=50):
        """
        初始化AzGames采集器
        
        Args:
            max_games_limit (int): 最大采集游戏数量限制
        """
        self.max_games_limit = max_games_limit
        self.should_stop = False
        self.driver = None
        self.logger = logging.getLogger(__name__)
        
        # 使用固定的搜索引擎User-Agent，避免频繁变化
        self.fixed_user_agent = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
        
        # 初始化requests session，使用固定UA
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

    def rotate_user_agent(self):
        """保持固定User-Agent，不再轮换"""
        # 为了保持兼容性，保留此方法但不执行任何操作
        self.logger.debug("使用固定UA策略，不进行轮换")

    def random_delay(self, min_seconds=2, max_seconds=8):
        """随机延时"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def stop_scraping(self):
        """停止采集"""
        self.should_stop = True
        if self.driver:
            self.driver.quit()

    def scrape_games(self, progress_callback=None, stop_flag=None):
        """
        采集AzGames.io游戏数据 - 新策略：先获取所有游戏列表，再逐个采集

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
                progress_callback("正在获取游戏列表...")

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
        获取所有游戏的基本信息列表（名称和URL）

        Args:
            progress_callback: 进度回调函数
            stop_flag: 停止标志函数

        Returns:
            list: [(game_name, game_url), ...] 游戏信息元组列表
        """
        game_list = []

        try:
            if progress_callback:
                progress_callback("使用requests方案获取游戏列表...")

            url = "https://azgames.io/new-games"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 查找游戏链接元素
            game_links = soup.select('.us-grid-game a.us-game-link')

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
                        game_url = 'https://azgames.io' + game_url

                    # 避免重复
                    if game_url in processed_urls:
                        continue

                    # 从链接内部的img元素获取游戏名称
                    img_element = link.find('img')
                    game_name = None

                    if img_element:
                        game_name = img_element.get('title') or img_element.get('alt')

                    if not game_name:
                        # 尝试从游戏标题div获取名称
                        title_element = link.find('span', class_='text-overflow')
                        if title_element:
                            game_name = title_element.get_text(strip=True)

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
                progress_callback(f"游戏列表获取完成，共 {len(game_list)} 个有效游戏")

        except Exception as e:
            self.logger.error(f"获取游戏列表失败: {str(e)}")
            if progress_callback:
                progress_callback(f"获取游戏列表失败: {str(e)}")

        return game_list

    def load_more_games(self, page_number):
        """
        加载更多游戏（点击More games按钮）

        Args:
            page_number (int): 页码

        Returns:
            bool: 是否成功加载更多
        """
        try:
            # 记录加载前的游戏数量
            initial_games = len(self.driver.find_elements(By.CSS_SELECTOR, ".us-grid-game a.us-game-link"))

            # 查找"More games"按钮
            try:
                more_button = self.driver.find_element(By.CSS_SELECTOR, "span.next_page")
                if more_button.is_displayed() and more_button.is_enabled():
                    # 执行JavaScript点击，模拟paging函数调用
                    self.driver.execute_script(f"paging({page_number})")
                    self.logger.info(f"执行paging({page_number})函数")
                else:
                    self.logger.info("More games按钮不可用")
                    return False
            except NoSuchElementException:
                # 如果没有找到按钮，尝试直接调用paging函数
                self.logger.info("未找到More games按钮，尝试直接调用paging函数")
                self.driver.execute_script(f"paging({page_number})")

            # 等待新内容加载
            time.sleep(5)

            # 检查是否有新游戏加载
            final_games = len(self.driver.find_elements(By.CSS_SELECTOR, ".us-grid-game a.us-game-link"))

            if final_games > initial_games:
                self.logger.info(f"成功加载第 {page_number} 页，游戏数量从 {initial_games} 增加到 {final_games}")
                return True
            else:
                self.logger.info(f"第 {page_number} 页没有新游戏加载")
                return False

        except Exception as e:
            self.logger.error(f"加载更多游戏失败: {str(e)}")
            return False

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
        if not game_url or 'azgames.io' not in game_url:
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
            '/images/'
        ]

        for pattern in invalid_patterns:
            if pattern in game_url.lower():
                self.logger.debug(f"过滤掉非游戏链接: {game_url}")
                return False

        # 确保是具体的游戏页面（通常是 /game-name 格式）
        if game_url.startswith('https://azgames.io/'):
            path = game_url.replace('https://azgames.io/', '')
        elif game_url.startswith('/'):
            path = game_url[1:]
        else:
            return False

        # 游戏页面通常是单层路径，不包含斜杠
        if '/' in path and not path.endswith('/'):
            self.logger.debug(f"过滤掉多层路径: {game_url}")
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
                    'iframe_url': "",  # azgames使用embed_url，这里保持空
                    'platform': 'azgames.io',
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

        Args:
            soup: BeautifulSoup对象
            game_url (str): 游戏页面URL
            html_content (str): 原始HTML内容

        Returns:
            str: embed URL
        """
        try:
            # 方法1: 查找HTML注释中的embed链接
            # <!-- <div class="az-games__embed-link">https://azgames.io/subway-moto.embed</div> -->
            from bs4 import Comment
            comments = soup.find_all(string=lambda text: isinstance(text, Comment) and 'az-games__embed-link' in text)
            for comment in comments:
                # 使用正则表达式提取URL
                embed_pattern = r'https://azgames\.io/[^<>\s"\']+\.embed'
                matches = re.findall(embed_pattern, str(comment))
                if matches:
                    embed_url = matches[0]
                    self.logger.info(f"通过HTML注释找到URL: {embed_url}")
                    return embed_url

            # 方法1.1: 如果没有找到Comment类型，尝试在整个HTML源码中查找注释
            search_content = html_content if html_content else str(soup)
            comment_pattern = r'<!--.*?az-games__embed-link.*?-->'
            comment_matches = re.findall(comment_pattern, search_content, re.DOTALL)
            for comment_match in comment_matches:
                embed_pattern = r'https://azgames\.io/[^<>\s"\']+\.embed'
                matches = re.findall(embed_pattern, comment_match)
                if matches:
                    embed_url = matches[0]
                    self.logger.info(f"通过HTML注释源码找到URL: {embed_url}")
                    return embed_url

            # 方法2: 查找包含.embed的src属性
            # 格式: src="/subway-moto.embed"
            embed_elements = soup.find_all(['iframe', 'embed', 'object'])
            for element in embed_elements:
                src = element.get('src', '')
                if src and '.embed' in src:
                    # 如果是相对路径，拼接主域名
                    if src.startswith('/'):
                        embed_url = 'https://azgames.io' + src
                    else:
                        embed_url = src
                    self.logger.info(f"通过embed元素找到URL: {embed_url}")
                    return embed_url

            # 方法3: 在JavaScript中查找.embed URL
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    # 查找包含.embed的字符串
                    embed_pattern = r'["\']([^"\']*\.embed)["\']'
                    matches = re.findall(embed_pattern, script.string)
                    for match in matches:
                        if match.startswith('/'):
                            embed_url = 'https://azgames.io' + match
                        else:
                            embed_url = match
                        self.logger.info(f"通过JavaScript找到URL: {embed_url}")
                        return embed_url

            # 方法3.1: 在整个HTML内容中搜索.embed URL
            if html_content:
                # 搜索所有可能的.embed URL模式
                embed_patterns = [
                    r'https://azgames\.io/[^<>\s"\']+\.embed',
                    r'/[^<>\s"\']+\.embed',
                    r'"([^"]*\.embed)"',
                    r"'([^']*\.embed)'",
                ]

                for pattern in embed_patterns:
                    matches = re.findall(pattern, html_content)
                    for match in matches:
                        if match.startswith('/'):
                            embed_url = 'https://azgames.io' + match
                        elif match.startswith('http'):
                            embed_url = match
                        else:
                            embed_url = 'https://azgames.io/' + match

                        # 验证URL格式
                        if '.embed' in embed_url and 'azgames.io' in embed_url:
                            self.logger.info(f"通过HTML内容搜索找到URL: {embed_url}")
                            return embed_url

            # 方法4: 根据游戏URL推断embed URL
            # 例如: https://azgames.io/subway-moto -> https://azgames.io/subway-moto.embed
            if game_url.startswith('https://azgames.io/'):
                game_path = game_url.replace('https://azgames.io/', '')
                embed_url = f"https://azgames.io/{game_path}.embed"

                # 验证这个URL是否存在
                try:
                    response = self.session.head(embed_url, timeout=10)
                    if response.status_code == 200:
                        self.logger.info(f"通过推断找到URL: {embed_url}")
                        return embed_url
                except:
                    pass

            return None

        except Exception as e:
            self.logger.error(f"提取embed URL时出错: {str(e)}")
            return None

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
                progress_callback("使用requests方案采集AzGames数据...")

            url = "https://azgames.io/new-games"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 查找游戏链接元素 - 使用更精确的选择器
            game_links = soup.select('.us-grid-game a.us-game-link')

            if progress_callback:
                progress_callback(f"找到 {len(game_links)} 个游戏")

            for i, link in enumerate(game_links):
                if stop_flag and stop_flag():
                    break

                try:
                    # 获取游戏链接
                    game_url = link.get('href')
                    if not game_url:
                        continue

                    # 如果是相对路径，拼接主域名
                    if game_url.startswith('/'):
                        game_url = 'https://azgames.io' + game_url

                    # 从链接内部的img元素获取游戏名称
                    img_element = link.find('img')
                    game_name = None

                    if img_element:
                        game_name = img_element.get('title') or img_element.get('alt')

                    if not game_name:
                        # 尝试从游戏标题div获取名称
                        title_element = link.find('span', class_='text-overflow')
                        if title_element:
                            game_name = title_element.get_text(strip=True)

                    # 如果还是没有找到游戏名称，跳过这个链接
                    if not game_name:
                        continue

                    if self.is_valid_game_entry(game_name, game_url):
                        if progress_callback:
                            progress_callback(f"正在处理游戏 {i+1}/{len(game_links)}: {game_name}")

                        # 获取游戏详情
                        game_data = self.scrape_game_detail(game_url, game_name)
                        if game_data:
                            games.append(game_data)

                            if progress_callback:
                                progress_callback(f"成功采集游戏: {game_name}", len(games))

                        # 随机延时
                        self.random_delay(3, 8)

                        # 限制采集数量
                        max_games = getattr(self, 'test_limit', None) or self.max_games_limit
                        if max_games and len(games) >= max_games:
                            if progress_callback:
                                progress_callback(f"已达到采集数量限制 ({max_games})")
                            break

                except Exception as e:
                    self.logger.error(f"处理游戏时出错: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"requests采集失败: {str(e)}")
            if progress_callback:
                progress_callback(f"采集错误: {str(e)}")

        return games
