#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端口检测模块
用于检测可用端口
"""

import socket
import logging


class PortDetector:
    """端口检测器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def is_port_available(self, port, host='localhost'):
        """
        检测指定端口是否可用
        
        Args:
            port (int): 端口号
            host (str): 主机地址，默认为localhost
            
        Returns:
            bool: 端口是否可用
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0  # 连接失败说明端口可用
        except Exception as e:
            self.logger.error(f"检测端口 {port} 时发生错误: {str(e)}")
            return False
            
    def find_available_port(self, start_port=7897, max_attempts=100):
        """
        从指定端口开始查找可用端口
        
        Args:
            start_port (int): 起始端口号
            max_attempts (int): 最大尝试次数
            
        Returns:
            int: 可用的端口号，如果找不到则返回None
        """
        for port in range(start_port, start_port + max_attempts):
            if self.is_port_available(port):
                self.logger.info(f"找到可用端口: {port}")
                return port
                
        self.logger.warning(f"在 {start_port}-{start_port + max_attempts} 范围内未找到可用端口")
        return None
        
    def get_port_info(self, port, host='localhost'):
        """
        获取端口详细信息
        
        Args:
            port (int): 端口号
            host (str): 主机地址
            
        Returns:
            dict: 端口信息
        """
        info = {
            'port': port,
            'host': host,
            'available': self.is_port_available(port, host),
            'service': self._get_service_name(port)
        }
        
        return info
        
    def _get_service_name(self, port):
        """
        获取端口对应的服务名称
        
        Args:
            port (int): 端口号
            
        Returns:
            str: 服务名称
        """
        try:
            return socket.getservbyport(port)
        except OSError:
            return "unknown"
