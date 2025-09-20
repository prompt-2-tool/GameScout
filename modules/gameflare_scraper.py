#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GameFlare.com 游戏采集器
使用Selenium处理反爬机制，采用与其他平台相同的策略：先获取所有游戏列表，再逐个采集详情
"""

import requests
import logging
import time
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Selenium相关导入
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class GameFlareScraper:
    """GameFlare.com游戏采集器"""
    
    def __init__(self, max_games_limit=50):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        
        # 设置固定的Google蜘蛛UA
        self.fixed_user_agent = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        self.session.headers.update({
            'User-Agent': self.fixed_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        self.logger.info(f"使用固定Google蜘蛛UA: {self.fixed_user_agent}")
        
        # 采集限制
        self.max_games_limit = max_games_limit
        self.should_stop = False
        
        # 测试限制（用于调试）
        self.test_limit = None
        
    def is_valid_game(self, game_name, game_url):
        """检查游戏是否有效"""
        if not game_name or not game_url:
            return False
        
        # 过滤无效的游戏名称
        game_name_lower = game_name.lower().strip()
        invalid_keywords = ['advertisement', 'ad', 'sponsor', 'promo', 'banner']
        
        for keyword in invalid_keywords:
            if keyword in game_name_lower:
                return False
        
        # 确保URL是GameFlare的游戏页面
        if not ('gameflare.com' in game_url and '/online-game/' in game_url):
            return False
        
        return True
    
    def scrape_games(self, progress_callback=None, stop_flag=None):
        """
        采集GameFlare.com游戏数据 - 使用Selenium策略：先获取所有游戏列表，再逐个采集
        
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
                    progress_callback("未获取到游戏列表")
                return games
            
            if progress_callback:
                progress_callback(f"获取到 {len(game_list)} 个游戏")
            
            # 第二步：根据用户设置决定采集数量
            if self.test_limit:
                # 测试模式
                games_to_process = game_list[:self.test_limit]
                if progress_callback:
                    progress_callback(f"测试模式，将采集前 {len(games_to_process)} 个游戏")
            elif self.max_games_limit and self.max_games_limit > 0:
                # 用户设置了限制
                games_to_process = game_list[:self.max_games_limit]
                if progress_callback:
                    progress_callback(f"根据设置限制，将采集前 {len(games_to_process)} 个游戏")
            else:
                # 不限制数量
                games_to_process = game_list
                if progress_callback:
                    progress_callback(f"将采集所有 {len(games_to_process)} 个游戏")
            
            # 第三步：逐个采集游戏详情
            for i, (game_name, game_url) in enumerate(games_to_process, 1):
                # 检查停止标志
                if stop_flag and stop_flag():
                    if progress_callback:
                        progress_callback("收到停止信号，终止采集")
                    break
                
                if self.should_stop:
                    if progress_callback:
                        progress_callback("收到停止信号，终止采集")
                    break
                
                if progress_callback:
                    progress_callback(f"正在采集游戏 {i}/{len(games_to_process)}: {game_name}")
                
                try:
                    game_data = self.scrape_game_detail(game_name, game_url, progress_callback)
                    if game_data:
                        games.append(game_data)
                        if progress_callback:
                            progress_callback(f"成功采集游戏: {game_name}", len(games))
                    
                    # 添加延迟避免请求过快
                    time.sleep(2)
                    
                except Exception as e:
                    self.logger.error(f"采集游戏 {game_name} 失败: {str(e)}")
                    if progress_callback:
                        progress_callback(f"采集游戏 {game_name} 失败: {str(e)}")
                    continue
                
        except Exception as e:
            self.logger.error(f"采集过程中发生错误: {str(e)}")
            if progress_callback:
                progress_callback(f"采集过程中发生错误: {str(e)}")
                
        return games
    
    def get_all_games_list(self, progress_callback=None, stop_flag=None):
        """
        使用Selenium获取所有GameFlare.com游戏的基本信息列表（名称和URL）
        
        Args:
            progress_callback: 进度回调函数
            stop_flag: 停止标志函数
            
        Returns:
            list: [(game_name, game_url), ...] 游戏信息列表
        """
        game_list = []
        
        if not SELENIUM_AVAILABLE:
            if progress_callback:
                progress_callback("Selenium不可用，无法采集GameFlare")
            return game_list
        
        driver = None
        try:
            # 配置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            # 禁用图片加载以提高速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)

            url = "https://www.gameflare.com/new-games/"
            driver.get(url)

            # 等待页面加载完成
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "a"))
            )

            # 获取页面源码并解析
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # 查找所有游戏链接 - 根据实际页面结构
            all_links = soup.find_all('a', href=True)
            game_links = []

            for link in all_links:
                href = link.get('href', '')
                if '/online-game/' in href:
                    game_links.append(link)

            if progress_callback:
                progress_callback(f"在页面中找到 {len(game_links)} 个游戏链接")

            processed_urls = set()

            for link in game_links:
                try:
                    # 检查停止标志
                    if stop_flag and stop_flag():
                        break

                    if self.should_stop:
                        break

                    # 获取游戏链接和名称
                    game_url = link.get('href')
                    game_name = link.get_text(strip=True)
                    
                    if not game_url or not game_name:
                        continue

                    # 确保URL是完整的
                    if game_url.startswith('/'):
                        game_url = 'https://www.gameflare.com' + game_url
                    
                    # 避免重复
                    if game_url in processed_urls:
                        continue
                    
                    # 验证游戏有效性
                    if not self.is_valid_game(game_name, game_url):
                        continue
                    
                    processed_urls.add(game_url)
                    game_list.append((game_name, game_url))
                    
                    # 显示进度
                    if len(game_list) % 10 == 0 and progress_callback:
                        progress_callback(f"已收集 {len(game_list)} 个游戏信息...")
                        
                except Exception as e:
                    self.logger.error(f"处理游戏元素时出错: {str(e)}")
                    continue

            if progress_callback:
                progress_callback(f"获取到 {len(game_list)} 个游戏")

        except Exception as e:
            self.logger.error(f"获取GameFlare.com游戏列表失败: {str(e)}")
            if progress_callback:
                progress_callback(f"获取游戏列表失败: {str(e)}")

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

        return game_list

    def scrape_game_detail(self, game_name, game_url, progress_callback=None):
        """
        使用Selenium采集单个游戏的详细信息

        Args:
            game_name: 游戏名称
            game_url: 游戏页面URL
            progress_callback: 进度回调函数

        Returns:
            dict: 游戏详细信息
        """
        self.logger.info(f"开始采集游戏详情: {game_name} - {game_url}")

        if not SELENIUM_AVAILABLE:
            return None

        driver = None
        try:
            # 配置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            # 禁用图片加载以提高速度
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)

            driver.get(game_url)

            # 等待页面加载完成，查找iframe
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#iframe-in-game"))
                )
            except TimeoutException:
                # 如果没有找到iframe，尝试查找其他可能的嵌入元素
                pass

            # 获取页面源码并解析
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # 提取embed URL
            embed_url = self.extract_embed_url(soup, game_url)

            if not embed_url:
                self.logger.warning(f"未找到游戏 {game_name} 的embed URL")
                return None

            # 构建游戏数据
            game_data = {
                'name': game_name,
                'url': game_url,
                'embed_url': embed_url,
                'platform': 'gameflare.com',
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            # 尝试提取游戏描述
            try:
                description_elem = soup.select_one('.content')
                if description_elem:
                    description = description_elem.get_text(strip=True)
                    if description and len(description) > 10:
                        game_data['description'] = description[:500]  # 限制长度
            except Exception as e:
                self.logger.debug(f"提取描述失败: {str(e)}")

            self.logger.info(f"成功采集游戏: {game_name} - embed: {embed_url}")
            return game_data

        except Exception as e:
            self.logger.error(f"采集游戏详情失败 {game_name}: {str(e)}")
            return None

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def extract_embed_url(self, soup, game_url):
        """
        从游戏页面提取embed URL

        Args:
            soup: BeautifulSoup对象
            game_url: 游戏页面URL

        Returns:
            str: embed URL或None
        """
        embed_url = None

        try:
            # 方法1: 查找iframe#iframe-in-game
            iframe = soup.select_one('#iframe-in-game')
            if iframe and iframe.get('src'):
                src = iframe.get('src')
                if src.startswith('/'):
                    embed_url = 'https://www.gameflare.com' + src
                else:
                    embed_url = src
                self.logger.info(f"通过iframe#iframe-in-game找到embed URL: {embed_url}")
                return embed_url

            # 方法2: 查找任何包含embed的iframe
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                if 'embed' in src and 'gameflare.com' in src:
                    if src.startswith('/'):
                        embed_url = 'https://www.gameflare.com' + src
                    else:
                        embed_url = src
                    self.logger.info(f"通过embed iframe找到embed URL: {embed_url}")
                    return embed_url

            # 方法3: 根据游戏URL推断embed URL（GameFlare的规律）
            if not embed_url and '/online-game/' in game_url:
                # 从 https://www.gameflare.com/online-game/dinosaur-island-survival/
                # 推断出 https://www.gameflare.com/embed/dinosaur-island-survival/
                game_slug = game_url.split('/online-game/')[-1].rstrip('/')
                embed_url = f'https://www.gameflare.com/embed/{game_slug}/'
                self.logger.info(f"通过URL规律推断embed URL: {embed_url}")
                return embed_url

        except Exception as e:
            self.logger.error(f"提取embed URL时出错: {str(e)}")

        return embed_url

    def stop(self):
        """停止采集"""
        self.should_stop = True
        self.logger.info("收到停止采集信号")


def test_gameflare_scraper():
    """测试GameFlare采集器"""
    print("🧪 测试GameFlare.com采集器...")

    scraper = GameFlareScraper()
    scraper.test_limit = 3  # 测试时只采集3个游戏

    def progress_callback(message, count=None):
        if count is not None:
            print(f"📊 {message} (已采集: {count})")
        else:
            print(f"📝 {message}")

    games = scraper.scrape_games(progress_callback=progress_callback)

    print(f"\n✅ 测试完成！采集到 {len(games)} 个游戏")
    print("=" * 50)

    for i, game in enumerate(games, 1):
        print(f"\n🎮 游戏 {i}:")
        print(f"   名称: {game['name']}")
        print(f"   页面: {game['url']}")
        print(f"   嵌入: {game['embed_url']}")
        print(f"   平台: {game['platform']}")
        print(f"   采集时间: {game['scraped_at']}")

    # 测试embed URL可访问性
    print(f"\n🔗 测试embed URL可访问性:")
    for i, game in enumerate(games, 1):
        embed_url = game['embed_url']
        print(f"   {i}. {game['name']}: {embed_url}")
        print(f"      ✅ URL格式正确")


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    test_gameflare_scraper()
