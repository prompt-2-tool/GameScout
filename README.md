# GameScout - 游戏采集工具

一个功能强大的游戏数据采集工具，支持多个游戏平台的数据采集，提供友好的GUI界面和完整的数据管理功能。

## 功能特性

- 🎮 支持多个游戏平台数据采集
- 🔍 智能提取游戏名称、页面链接和iframe地址
- 🌐 自动端口检测（默认7897）
- 📊 实时进度显示和详细日志记录
- 💾 双重数据存储（JSON + SQLite）
- 📤 多格式数据导出（JSON/CSV）
- 🔄 智能去重功能，避免重复数据
- 📝 Prompt模板导出，支持增量和全量导出
- 🖥️ 现代化GUI界面，统一设计风格
- 🛠️ 手动获取功能，支持单个游戏链接处理
- 📦 一键打包成独立EXE文件

## 安装说明

### 推荐方法: 直接使用EXE文件
下载 `dist/GameScout.exe` 文件，双击即可运行，无需安装Python环境。

### 开发环境安装
```bash
# 克隆项目
git clone <repository-url>
cd GameScout

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 核心依赖包
- requests - HTTP请求库
- beautifulsoup4 - HTML解析库
- selenium - 浏览器自动化
- webdriver-manager - WebDriver管理
- pyinstaller - 打包工具

## 使用方法

### 运行程序
```bash
# 开发环境
python main.py

# 或直接运行EXE文件
GameScout.exe
```

### 主要功能模块

#### 1. 多平台采集
- 支持4个游戏平台的数据采集
- 每个平台独立的采集界面和日志
- 智能采集策略，自动处理反爬机制
- 可设置采集数量限制

#### 2. 数据管理
- **查看数据**: 表格形式展示采集的游戏信息
- **智能去重**: 自动检测并跳过重复游戏
- **数据导出**: 支持JSON/CSV格式，全量/增量导出
- **数据统计**: 显示采集成功、跳过重复的详细统计

#### 3. Prompt导出
- **模板系统**: 内置多种prompt模板（标准版、简洁版、详细版等）
- **增量导出**: 仅导出最近24小时新增的游戏数据
- **全量导出**: 导出所有历史采集数据
- **格式化输出**: 生成结构化的TXT文件，便于后续处理

#### 4. 手动获取
- 支持输入单个游戏页面URL
- 快速提取iframe地址
- 一键复制格式化结果
- 支持多个平台的URL解析

### 采集流程
1. 访问游戏平台列表页面
2. 智能提取游戏链接和名称
3. 逐个访问游戏详情页面
4. 多策略解析并提取iframe地址
5. 去重检查后保存到本地数据库

## 数据格式

采集的游戏数据包含以下字段：
```json
{
  "name": "游戏名称",
  "url": "游戏页面URL",
  "embed_url": "嵌入游戏地址",
  "iframe_url": "iframe游戏地址",
  "platform": "平台名称",
  "scraped_at": "采集时间戳"
}
```

### 导出格式

#### JSON导出示例
```json
[
  {
    "name": "示例游戏",
    "url": "https://example.com/game",
    "embed_url": "https://example.com/game.embed",
    "iframe_url": "https://example.com/embed/game",
    "platform": "platform.io",
    "scraped_at": "2025-09-20 10:30:00"
  }
]
```

#### Prompt导出示例
```
# GameScout Prompt导出 - 本次新增数据
# 导出时间: 2025-09-20 10:30:00
# 游戏数量: 5

1. 学习下demo.php、开发指南.md，然后严格按照demo.php以及开发指南.md，帮我开发下面这个游戏页面：
游戏名称： 示例游戏
FAQ等信息参考：https://example.com/game
<iframe>引入链接：https://example.com/embed/game

2. ...
```

## 打包成EXE

```bash
python build.py
```

打包后的文件位于 `dist/GameScout.exe`

## 项目结构

```
GameScout/
├── main.py                    # 主程序入口，GUI界面
├── build.py                   # 打包脚本
├── requirements.txt           # 依赖包列表
├── logo.ico                   # 程序图标
├── modules/                   # 功能模块
│   ├── __init__.py
│   ├── port_detector.py       # 端口检测模块
│   ├── game_scraper.py        # 通用游戏采集基类
│   ├── azgames_scraper.py     # AzGames平台采集器
│   ├── zapgames_scraper.py    # ZapGames平台采集器
│   ├── gameflare_scraper.py   # GameFlare平台采集器
│   └── data_manager.py        # 数据管理模块
├── data/                      # 数据存储目录
│   ├── games.json             # JSON数据文件
│   └── games.db               # SQLite数据库
├── dist/                      # 打包输出目录
│   ├── GameScout.exe          # 独立可执行文件
│   └── data/                  # 数据目录
└── README.md                  # 项目说明文档
```

## 技术特性

### 智能采集策略
- **多重降级机制**: requests → Selenium自动切换
- **反爬虫处理**: 智能User-Agent轮换，延时控制
- **错误恢复**: 网络异常自动重试，断点续传
- **资源优化**: 内存管理，进程池控制

### 数据安全
- **双重存储**: JSON + SQLite双重备份
- **事务处理**: 确保数据一致性
- **去重算法**: 智能检测重复数据
- **增量更新**: 只处理新增数据，提高效率

## 注意事项

1. **浏览器要求**: 需要Chrome浏览器支持Selenium自动化
2. **网络环境**: 需要稳定的网络连接访问目标平台
3. **采集频率**: 内置智能延时机制，避免对服务器造成压力
4. **数据备份**: 建议定期备份data目录中的重要数据
5. **合规使用**: 请遵守目标网站的robots.txt和使用条款

## 常见问题

### Q: EXE文件无法运行？
A: 请检查Windows Defender或杀毒软件是否误报，添加信任即可

### Q: Chrome WebDriver错误？
A: 确保已安装Chrome浏览器，程序会自动下载匹配的WebDriver

### Q: 采集中断怎么办？
A: 程序支持断点续传，重新启动采集会从中断处继续

### Q: 数据导出失败？
A: 检查data目录权限，确保程序有读写权限

### Q: 手动获取功能无响应？
A: 检查输入的URL格式是否正确，确保网络连接正常

## 开发说明

### 添加新平台支持
1. 继承 `GameScraper` 基类创建新的采集器
2. 实现 `scrape_games_list()` 和 `scrape_game_detail()` 方法
3. 在 `main.py` 中添加对应的GUI标签页
4. 更新数据管理器支持新平台

### 自定义Prompt模板
1. 修改 `main.py` 中的 `prompt_templates` 字典
2. 添加新的模板变量和格式化规则
3. 更新 `generate_prompts()` 方法支持新字段

### 扩展导出功能
1. 在 `data_manager.py` 中添加新的导出格式
2. 修改 `export_games()` 方法支持新格式
3. 更新GUI界面添加新的导出选项

## 技术架构

### 核心模块
- **GameScraper**: 采集器基类，定义通用接口
- **DataManager**: 数据管理器，处理存储和导出
- **PortDetector**: 端口检测器，自动寻找可用端口
- **GUI**: 基于Tkinter的现代化界面

### 设计模式
- **策略模式**: 不同平台使用不同的采集策略
- **工厂模式**: 动态创建采集器实例
- **观察者模式**: GUI实时更新采集状态
- **单例模式**: 数据管理器确保数据一致性

## 许可证

本项目仅供学习和研究使用，请遵守相关网站的使用条款和法律法规。

## 更新日志

### v2.0.0 (2025-09-20)
- ✨ 新增多平台支持（4个游戏平台）
- ✨ 智能去重功能，避免重复数据
- ✨ Prompt模板导出，支持增量/全量导出
- ✨ 手动获取功能，支持单个URL处理
- 🎨 全新统一的GUI设计风格
- 🔧 优化采集策略，提高成功率

---

## 作者

**Prompt2Tool** - [prompt2tool.com](https://prompt2tool.com)

专注于AI工具开发和自动化解决方案