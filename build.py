#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GameScout 打包脚本
使用PyInstaller打包成EXE文件
"""

import subprocess
import sys
import os
import shutil


def build_exe():
    """打包成EXE文件"""
    print("正在打包成EXE文件...")
    
    # PyInstaller命令
    cmd = [
        "pyinstaller",
        "--onefile",  # 打包成单个文件
        "--windowed",  # 无控制台窗口
        "--name=GameScout",  # 程序名称
        "--icon=logo.ico",  # 图标文件（如果有的话）
        "--add-data=modules;modules",  # 包含modules目录
        "--hidden-import=selenium",
        "--hidden-import=webdriver_manager",
        "--hidden-import=beautifulsoup4",
        "--hidden-import=requests",
        "main.py"
    ]
    
    try:
        # 如果没有图标文件，移除图标参数
        if not os.path.exists("logo.ico"):
            cmd.remove("--icon=logo.ico")
            
        subprocess.check_call(cmd)
        print("打包完成！")
        print("EXE文件位置: dist/GameScout.exe")
        
        # 复制必要文件到dist目录
        if os.path.exists("dist"):
            # 创建data目录
            data_dir = os.path.join("dist", "data")
            os.makedirs(data_dir, exist_ok=True)
            
            print("打包成功！可以在dist目录找到GameScout.exe")
            
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        return False
        
    except FileNotFoundError:
        print("PyInstaller未安装，请先运行: pip install pyinstaller")
        return False
        
    return True


def clean_build():
    """清理构建文件"""
    print("清理构建文件...")
    
    dirs_to_remove = ["build", "__pycache__"]
    files_to_remove = ["GameScout.spec"]
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"已删除: {dir_name}")
            
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"已删除: {file_name}")


def main():
    """主函数"""
    print("=" * 50)
    print("GameScout 游戏采集工具 - 打包程序")
    print("=" * 50)
    
    # 检查main.py是否存在
    if not os.path.exists("main.py"):
        print("错误: 未找到main.py文件")
        return
        
    # 打包
    if build_exe():
        print("\n打包成功！")
        
        # 询问是否清理构建文件
        response = input("是否清理构建文件？(y/n): ")
        if response.lower() in ['y', 'yes']:
            clean_build()
    else:
        print("打包失败！")


if __name__ == "__main__":
    main()
