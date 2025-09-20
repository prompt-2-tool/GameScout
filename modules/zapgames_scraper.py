#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZapGames.io 游戏采集器
采用与itch.io和AzGames相同的新策略：先获取所有游戏列表，再逐个采集详情
"""

import requests
import logging
import time
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class ZapGamesScraper:
    """ZapGames.io游戏采集器"""
    
    def __init__(self, max_games_limit=50):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        
        # 使用Google蜘蛛UA，避免频繁变化
        self.fixed_user_agent = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
        
        self.session.headers.update({
            'User-Agent': self.fixed_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        
        self.should_stop = False
        self.max_games_limit = max_games_limit
        self.logger.info(f"使用固定Google蜘蛛UA: {self.fixed_user_agent}")
    
    def random_delay(self, min_seconds=1, max_seconds=3):
        """随机延时，模拟真人行为"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def is_valid_game_entry(self, game_name, game_url):
        """验证游戏条目是否有效"""
        if not game_name or not game_url:
            return False
        
        # 过滤掉明显无效的条目
        invalid_keywords = ['advertisement', 'promo', 'sponsor', 'ad-']
        game_name_lower = game_name.lower()
        
        for keyword in invalid_keywords:
            if keyword in game_name_lower:
                return False
        
        # 确保URL是ZapGames的游戏页面
        if not game_url.startswith('/') and 'zapgames.io' not in game_url:
            return False
        
        return True
    
    def scrape_games(self, progress_callback=None, stop_flag=None):
        """
        采集ZapGames.io游戏数据 - 新策略：先获取所有游戏列表，再逐个采集
        
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
            
            # 第三步：逐个采集游戏详情（不再变化UA，使用固定的浏览器UA）
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
        获取所有ZapGames.io游戏的基本信息列表（名称和URL）
        
        Args:
            progress_callback: 进度回调函数
            stop_flag: 停止标志函数
            
        Returns:
            list: [(game_name, game_url), ...] 游戏信息元组列表
        """
        game_list = []
        
        try:
            # 不输出技术细节到用户界面

            url = "https://zapgames.io/new"
            
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')  # 使用response.text而不是content

                # 检查是否获取到了有效内容
                game_links = soup.select('a.GameThumb_gameThumbLinkDesktop__wcir5')
                if len(game_links) == 0:
                    # 如果没有找到游戏链接，可能需要JavaScript渲染，使用Selenium
                    soup = self.get_page_with_selenium(url, progress_callback)
                    if not soup:
                        raise Exception("获取游戏列表失败")

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    # 如果requests被拒绝，尝试使用Selenium
                    soup = self.get_page_with_selenium(url, progress_callback)
                    if not soup:
                        raise Exception("获取游戏列表失败")
                else:
                    raise

            # 查找游戏链接元素 - 根据提供的HTML结构
            game_links = soup.select('a.GameThumb_gameThumbLinkDesktop__wcir5')

            if progress_callback:
                progress_callback(f"在页面中找到 {len(game_links)} 个游戏链接")

            processed_urls = set()
            
            for link in game_links:
                if stop_flag and stop_flag():
                    break

                try:
                    # 获取游戏链接和名称
                    game_url = link.get('href')

                    # 从游戏标题容器中获取游戏名称
                    title_container = link.select_one('.GameThumb_gameThumbTitleContainer__J1K4D')
                    if title_container:
                        # 获取纯净的游戏名称，去掉标签（如"Top rated"、"Hot"等）
                        full_text = title_container.get_text(strip=True)

                        # 去掉常见的标签前缀
                        prefixes_to_remove = ['Top rated', 'Hot', 'Trending', 'New']
                        game_name = full_text
                        for prefix in prefixes_to_remove:
                            if game_name.startswith(prefix):
                                game_name = game_name[len(prefix):].strip()
                                break
                    else:
                        # 备用方案：从alt属性获取
                        img = link.select_one('img')
                        if img and img.get('alt'):
                            alt_text = img.get('alt')
                            # 从"Play Math Lava: Tower Race game"中提取游戏名
                            if alt_text.startswith('Play ') and alt_text.endswith(' game'):
                                game_name = alt_text[5:-5]  # 去掉"Play "和" game"
                            else:
                                game_name = alt_text
                        else:
                            continue
                    
                    if not game_url or not game_name:
                        continue

                    # 如果是相对路径，拼接主域名
                    if game_url.startswith('/'):
                        full_game_url = 'https://zapgames.io' + game_url
                    else:
                        full_game_url = game_url

                    # 避免重复
                    if full_game_url in processed_urls:
                        continue
                    
                    # 验证游戏信息有效性
                    if self.is_valid_game_entry(game_name, game_url):
                        game_list.append((game_name, full_game_url))
                        processed_urls.add(full_game_url)
                        
                        if progress_callback and len(game_list) % 10 == 0:
                            progress_callback(f"已收集 {len(game_list)} 个游戏信息...")

                except Exception as e:
                    self.logger.error(f"处理游戏链接时出错: {str(e)}")
                    continue

            if progress_callback:
                progress_callback(f"获取到 {len(game_list)} 个游戏")

        except Exception as e:
            self.logger.error(f"获取ZapGames.io游戏列表失败: {str(e)}")
            if progress_callback:
                progress_callback(f"获取游戏列表失败: {str(e)}")

        return game_list

    def get_page_with_selenium(self, url, progress_callback=None):
        """
        使用Selenium获取页面内容（备用方案）

        Args:
            url: 页面URL
            progress_callback: 进度回调函数

        Returns:
            BeautifulSoup: 页面解析对象，失败返回None
        """
        if not SELENIUM_AVAILABLE:
            self.logger.error("Selenium不可用，无法使用备用方案")
            return None

        driver = None
        try:
            # 不输出技术细节到用户界面

            # 配置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument(f'--user-agent={self.fixed_user_agent}')

            # 禁用图片加载以提高速度
            prefs = {"profile.managed_default_content_settings.images": 2}
            chrome_options.add_experimental_option("prefs", prefs)

            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)

            # 不输出技术细节到用户界面

            driver.get(url)

            # 等待页面加载完成
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".GameThumb_gameThumbLinkDesktop__wcir5"))
            )

            # 不输出技术细节到用户界面

            # 获取页面源码并解析
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            return soup

        except Exception as e:
            self.logger.error(f"Selenium获取页面失败: {str(e)}")
            if progress_callback:
                progress_callback(f"Selenium方案失败: {str(e)}")
            return None

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def scrape_game_detail(self, game_url, game_name):
        """
        采集单个游戏的详细信息，包括embed URL

        Args:
            game_url: 游戏页面URL
            game_name: 游戏名称

        Returns:
            dict: 游戏详细信息，如果失败返回None
        """
        try:
            self.logger.info(f"开始采集游戏详情: {game_name} - {game_url}")

            # 获取游戏详情页面
            response = self.session.get(game_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 提取embed URL - 查找iframe或embed元素
            embed_url = self.extract_embed_url(soup, game_url)

            if not embed_url:
                self.logger.warning(f"未找到有效的embed URL: {game_name}")
                return None

            # 验证embed URL是否可访问
            if not self.verify_embed_url(embed_url):
                self.logger.warning(f"embed URL无法访问: {embed_url}")
                return None

            # 提取其他游戏信息
            game_data = {
                'name': game_name,
                'url': game_url,
                'embed_url': embed_url,
                'platform': 'zapgames.io',
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            # 尝试提取游戏描述
            try:
                description_elem = soup.select_one('.game-description, .description, p')
                if description_elem:
                    game_data['description'] = description_elem.get_text(strip=True)[:500]  # 限制长度
            except:
                pass

            # 尝试提取游戏标签/类型
            try:
                tags = []
                tag_elements = soup.select('.tag, .category, .label')
                for tag_elem in tag_elements:
                    tag_text = tag_elem.get_text(strip=True)
                    if tag_text and len(tag_text) < 20:  # 过滤掉过长的文本
                        tags.append(tag_text)

                if tags:
                    game_data['tags'] = tags[:5]  # 最多保留5个标签
            except:
                pass

            self.logger.info(f"成功采集游戏: {game_name} - embed: {embed_url}")
            return game_data

        except Exception as e:
            self.logger.error(f"采集游戏详情失败 {game_name}: {str(e)}")
            return None

    def extract_embed_url(self, soup, game_url):
        """
        从游戏页面提取embed URL

        Args:
            soup: BeautifulSoup对象
            game_url: 游戏页面URL

        Returns:
            str: embed URL，如果未找到返回None
        """
        embed_url = None

        try:
            # 方法1: 查找iframe元素中的src属性
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                if src and '.embed' in src:
                    embed_url = src
                    self.logger.info(f"通过iframe元素找到embed URL: {embed_url}")
                    break

            # 方法2: 查找embed或object元素
            if not embed_url:
                embed_elements = soup.find_all(['embed', 'object'])
                for element in embed_elements:
                    src = element.get('src') or element.get('data', '')
                    if src and '.embed' in src:
                        embed_url = src
                        self.logger.info(f"通过embed/object元素找到embed URL: {embed_url}")
                        break

            # 方法3: 根据游戏URL推断embed URL（ZapGames的规律）
            if not embed_url:
                # 从 https://zapgames.io/im-not-a-robot 推断出 https://zapgames.io/im-not-a-robot.embed
                if 'zapgames.io/' in game_url:
                    embed_url = game_url + '.embed'
                    self.logger.info(f"通过URL规律推断embed URL: {embed_url}")

            # 确保embed URL是完整的URL
            if embed_url:
                if embed_url.startswith('/'):
                    embed_url = 'https://zapgames.io' + embed_url
                elif not embed_url.startswith('http'):
                    embed_url = 'https://zapgames.io/' + embed_url

                # 验证URL格式
                if 'zapgames.io' in embed_url and '.embed' in embed_url:
                    return embed_url
                else:
                    self.logger.warning(f"embed URL格式不正确: {embed_url}")
                    return None

        except Exception as e:
            self.logger.error(f"提取embed URL时出错: {str(e)}")

        return None

    def verify_embed_url(self, embed_url):
        """
        验证embed URL是否可访问

        Args:
            embed_url: embed URL

        Returns:
            bool: 是否可访问
        """
        try:
            response = self.session.head(embed_url, timeout=10)
            return response.status_code == 200
        except:
            # 如果HEAD请求失败，尝试GET请求
            try:
                response = self.session.get(embed_url, timeout=10)
                return response.status_code == 200
            except:
                return False

    def stop_scraping(self):
        """停止采集"""
        self.should_stop = True
        self.logger.info("收到停止采集信号")


def test_zapgames_scraper():
    """测试ZapGames采集器"""
    print("🧪 测试ZapGames.io采集器...")

    scraper = ZapGamesScraper()
    scraper.test_limit = 5  # 测试时只采集5个游戏

    def progress_callback(message, count=None):
        if count is not None:
            print(f"📊 {message} (已采集: {count})")
        else:
            print(f"📝 {message}")

    games = scraper.scrape_games(progress_callback=progress_callback)

    print(f"\n✅ 测试完成！采集到 {len(games)} 个游戏")

    for i, game in enumerate(games, 1):
        print(f"\n🎮 游戏 {i}:")
        print(f"   名称: {game['name']}")
        print(f"   页面: {game['url']}")
        print(f"   嵌入: {game['embed_url']}")
        if 'description' in game:
            print(f"   描述: {game['description'][:100]}...")
        if 'tags' in game:
            print(f"   标签: {', '.join(game['tags'])}")


if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    test_zapgames_scraper()
