#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据管理模块
用于保存和管理采集的游戏数据
"""

import json
import os
import sqlite3
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional


class DataManager:
    """数据管理器"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.json_file = os.path.join(data_dir, "games.json")
        self.db_file = os.path.join(data_dir, "games.db")
        self.logger = logging.getLogger(__name__)
        
        # 创建数据目录
        os.makedirs(data_dir, exist_ok=True)
        
        # 初始化数据库
        self.init_database()
        
    def init_database(self):
        """初始化SQLite数据库"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS games (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        embed_url TEXT,
                        iframe_url TEXT,
                        platform TEXT DEFAULT 'itch.io',
                        scraped_at TEXT NOT NULL,
                        UNIQUE(url, platform)
                    )
                ''')
                conn.commit()
                self.logger.info("数据库初始化成功")
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {str(e)}")
            
    def save_games(self, games: List[Dict], platform: str = None) -> Dict:
        """
        保存游戏数据，自动去重

        Args:
            games: 游戏数据列表
            platform: 平台名称

        Returns:
            Dict: 包含保存统计信息的字典 {'saved': int, 'duplicates': int, 'total': int}
        """
        try:
            # 过滤无效数据：必须有有效的iframe_url或embed_url
            valid_games = []
            for game in games:
                # 检查是否有有效的iframe_url或embed_url
                iframe_url = game.get('iframe_url', '')
                embed_url = game.get('embed_url', '')

                if (iframe_url and iframe_url.strip() and iframe_url not in ['null', 'None']) or \
                   (embed_url and embed_url.strip() and embed_url not in ['null', 'None']):
                    # 确保所有必需字段都存在
                    if 'name' not in game:
                        game['name'] = ''
                    if 'url' not in game:
                        game['url'] = ''
                    if 'embed_url' not in game:
                        game['embed_url'] = ''
                    if 'iframe_url' not in game:
                        game['iframe_url'] = ''
                    if 'scraped_at' not in game:
                        game['scraped_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

                    # 添加平台信息
                    if platform and 'platform' not in game:
                        game['platform'] = platform
                    elif 'platform' not in game:
                        game['platform'] = 'itch.io'  # 默认平台

                    valid_games.append(game)
                else:
                    self.logger.warning(f"跳过无效游戏数据: {game.get('name', '未知')} - 缺少有效的iframe_url或embed_url")

            if not valid_games:
                self.logger.warning("没有有效的游戏数据需要保存")
                return {'saved': 0, 'duplicates': 0, 'total': len(games)}

            # 去重处理
            result = self.save_with_deduplication(valid_games, platform)

            platform_info = f" ({platform})" if platform else ""
            self.logger.info(f"游戏保存完成{platform_info} - 总数: {result['total']}, 新增: {result['saved']}, 重复跳过: {result['duplicates']}")
            return result

        except Exception as e:
            self.logger.error(f"保存游戏数据失败: {str(e)}")
            return {'saved': 0, 'duplicates': 0, 'total': len(games)}

    def save_with_deduplication(self, games: List[Dict], platform: str = None) -> Dict:
        """
        保存游戏数据并进行去重处理

        Args:
            games: 游戏数据列表
            platform: 平台名称

        Returns:
            Dict: 保存统计信息
        """
        saved_count = 0
        duplicate_count = 0
        new_games = []

        try:
            # 获取现有游戏名称列表
            existing_names = set()
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                if platform:
                    cursor.execute('SELECT name FROM games WHERE platform = ?', (platform,))
                else:
                    cursor.execute('SELECT name FROM games')
                existing_names = {row[0].strip().lower() for row in cursor.fetchall()}

            # 检查每个游戏是否重复
            for game in games:
                game_name = game.get('name', '').strip()
                if not game_name:
                    continue

                # 使用小写进行比较，避免大小写差异
                if game_name.lower() not in existing_names:
                    new_games.append(game)
                    existing_names.add(game_name.lower())  # 添加到已存在列表，避免本次采集内部重复
                    saved_count += 1
                    self.logger.debug(f"新游戏: {game_name}")
                else:
                    duplicate_count += 1
                    self.logger.debug(f"重复游戏: {game_name}")

            # 保存新游戏
            if new_games:
                # 保存到JSON文件
                self.save_to_json(new_games)
                # 保存到SQLite数据库
                self.save_to_database(new_games)

            return {
                'saved': saved_count,
                'duplicates': duplicate_count,
                'total': len(games)
            }

        except Exception as e:
            self.logger.error(f"去重保存失败: {str(e)}")
            return {'saved': 0, 'duplicates': 0, 'total': len(games)}

    def save_to_json(self, games: List[Dict]):
        """保存到JSON文件"""
        # 加载现有数据
        existing_games = self.load_from_json()
        
        # 合并数据（避免重复）
        existing_urls = {game.get('url') for game in existing_games}
        new_games = [game for game in games if game.get('url') not in existing_urls]
        
        all_games = existing_games + new_games
        
        # 保存到文件
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(all_games, f, ensure_ascii=False, indent=2)
            
    def save_to_database(self, games: List[Dict]):
        """保存到SQLite数据库"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            for game in games:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO games (name, url, embed_url, iframe_url, platform, scraped_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        game.get('name', ''),
                        game.get('url', ''),
                        game.get('embed_url', ''),
                        game.get('iframe_url', ''),
                        game.get('platform', 'itch.io'),
                        game.get('scraped_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    ))
                except Exception as e:
                    self.logger.error(f"保存游戏到数据库失败 {game.get('name', '')}: {str(e)}")
                    
            conn.commit()
            
    def load_games(self, platform: str = None) -> List[Dict]:
        """
        加载游戏数据

        Args:
            platform: 平台名称，如果指定则只加载该平台的数据

        Returns:
            List[Dict]: 游戏数据列表
        """
        try:
            # 优先从数据库加载
            games = self.load_from_database(platform)
            if games:
                return games

            # 如果数据库为空，从JSON文件加载
            all_games = self.load_from_json()
            if platform:
                # 过滤指定平台的游戏
                return [game for game in all_games if game.get('platform') == platform]
            return all_games

        except Exception as e:
            self.logger.error(f"加载游戏数据失败: {str(e)}")
            return []
            
    def load_from_json(self) -> List[Dict]:
        """从JSON文件加载数据"""
        if not os.path.exists(self.json_file):
            return []
            
        try:
            with open(self.json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"从JSON文件加载数据失败: {str(e)}")
            return []
            
    def load_from_database(self, platform: str = None) -> List[Dict]:
        """从SQLite数据库加载数据"""
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()

                if platform:
                    cursor.execute('''
                        SELECT name, url, embed_url, iframe_url, platform, scraped_at
                        FROM games
                        WHERE platform = ?
                        ORDER BY scraped_at DESC
                    ''', (platform,))
                else:
                    cursor.execute('''
                        SELECT name, url, embed_url, iframe_url, platform, scraped_at
                        FROM games
                        ORDER BY scraped_at DESC
                    ''')

                rows = cursor.fetchall()
                games = []

                for row in rows:
                    games.append({
                        'name': row[0],
                        'url': row[1],
                        'embed_url': row[2],
                        'iframe_url': row[3],
                        'platform': row[4],
                        'scraped_at': row[5]
                    })

                return games
                
        except Exception as e:
            self.logger.error(f"从数据库加载数据失败: {str(e)}")
            return []

    def get_recent_games(self, platform: str = None, hours: int = 24) -> List[Dict]:
        """
        获取最近采集的游戏数据

        Args:
            platform: 平台名称
            hours: 最近多少小时内的数据

        Returns:
            List[Dict]: 最近采集的游戏数据列表
        """
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()

                # 计算时间阈值
                from datetime import datetime, timedelta
                threshold = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

                if platform:
                    cursor.execute('''
                        SELECT name, url, embed_url, iframe_url, platform, scraped_at
                        FROM games
                        WHERE platform = ? AND scraped_at >= ?
                        ORDER BY scraped_at DESC
                    ''', (platform, threshold))
                else:
                    cursor.execute('''
                        SELECT name, url, embed_url, iframe_url, platform, scraped_at
                        FROM games
                        WHERE scraped_at >= ?
                        ORDER BY scraped_at DESC
                    ''', (threshold,))

                games = []
                for row in cursor.fetchall():
                    games.append({
                        'name': row[0],
                        'url': row[1],
                        'embed_url': row[2],
                        'iframe_url': row[3],
                        'platform': row[4],
                        'scraped_at': row[5]
                    })

                return games

        except Exception as e:
            self.logger.error(f"获取最近游戏数据失败: {str(e)}")
            return []

    def export_games(self, platform: str = None, format='json', recent_only: bool = False) -> Optional[str]:
        """
        导出游戏数据

        Args:
            platform: 平台名称，如果指定则只导出该平台的数据
            format: 导出格式 ('json', 'csv')
            recent_only: 是否只导出最近24小时的数据

        Returns:
            str: 导出文件路径
        """
        # 根据选项获取数据
        if recent_only:
            games = self.get_recent_games(platform, hours=24)
            export_type = "recent"
        else:
            games = self.load_games(platform)
            export_type = "all"

        if not games:
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        platform_suffix = f"_{platform}" if platform else ""
        type_suffix = f"_{export_type}"

        if format == 'json':
            filename = f"games_export{platform_suffix}{type_suffix}_{timestamp}.json"
            filepath = os.path.join(self.data_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(games, f, ensure_ascii=False, indent=2)

        elif format == 'csv':
            import csv
            filename = f"games_export{platform_suffix}{type_suffix}_{timestamp}.csv"
            filepath = os.path.join(self.data_dir, filename)

            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                if games:
                    writer = csv.DictWriter(f, fieldnames=games[0].keys())
                    writer.writeheader()
                    writer.writerows(games)

        else:
            raise ValueError(f"不支持的导出格式: {format}")

        export_info = "最近24小时" if recent_only else "全部"
        platform_info = f" ({platform})" if platform else ""
        self.logger.info(f"{export_info}数据{platform_info}已导出到: {filepath} (共{len(games)}条)")
        return filepath
        
    def get_statistics(self) -> Dict:
        """
        获取数据统计信息
        
        Returns:
            Dict: 统计信息
        """
        games = self.load_games()
        
        stats = {
            'total_games': len(games),
            'games_with_iframe': len([g for g in games if g.get('iframe_url')]),
            'games_without_iframe': len([g for g in games if not g.get('iframe_url')]),
            'last_scraped': None
        }
        
        if games:
            # 找到最新的采集时间
            scraped_times = [g.get('scraped_at') for g in games if g.get('scraped_at')]
            if scraped_times:
                stats['last_scraped'] = max(scraped_times)
                
        return stats
        
    def clear_data(self):
        """清空所有数据"""
        try:
            # 清空JSON文件
            if os.path.exists(self.json_file):
                os.remove(self.json_file)
                
            # 清空数据库
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM games')
                conn.commit()
                
            self.logger.info("数据已清空")
            
        except Exception as e:
            self.logger.error(f"清空数据失败: {str(e)}")
            
    def search_games(self, keyword: str) -> List[Dict]:
        """
        搜索游戏
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            List[Dict]: 匹配的游戏列表
        """
        games = self.load_games()
        keyword = keyword.lower()
        
        results = []
        for game in games:
            name = game.get('name', '').lower()
            url = game.get('url', '').lower()
            
            if keyword in name or keyword in url:
                results.append(game)
                
        return results
