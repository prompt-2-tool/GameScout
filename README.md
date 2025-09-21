# GameScout - Game Data Scraping Tool

[中文版本](README_CN.md) | English

A powerful game data scraping tool that supports multiple gaming platforms with a user-friendly GUI interface and comprehensive data management features.

## Features

- 🎮 Multi-platform game data scraping support
- 🔍 Intelligent extraction of game names, page links, and iframe addresses
- 🌐 Automatic port detection (default 7897)
- 📊 Real-time progress display and detailed logging
- 💾 Dual data storage (JSON + SQLite)
- 📤 Multi-format data export (JSON/CSV)
- 🔄 Smart deduplication to avoid duplicate data
- 📝 Prompt template export with incremental and full export options
- 🖥️ Modern GUI interface with unified design
- 🛠️ Manual fetch feature for single game link processing
- 📦 One-click packaging to standalone EXE file


## Installation

### Recommended: Use Pre-built EXE
Download the `dist/GameScout.exe` file and double-click to run. No Python environment required.

### Development Environment Setup
```bash
# Clone the repository
git clone <repository-url>
cd GameScout

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Core Dependencies
- requests - HTTP request library
- beautifulsoup4 - HTML parsing library
- selenium - Browser automation
- webdriver-manager - WebDriver management
- pyinstaller - Packaging tool

## Usage

### Running the Application

```bash
# Development environment
python main.py

# Or run the EXE file directly
GameScout.exe
```

### Main Features

#### 1. Multi-Platform Scraping
- Support for 2 gaming platforms (Itch, AzGames) with automated batch scraping
- Independent scraping interface and logs for each platform
- Intelligent scraping strategies with automatic anti-bot handling
- Configurable scraping quantity limits

#### 2. Integrated Development Toolkit
- **8 Specialized Tools**: Direct browser access to professional game development tools
- **Iframe Compatibility Tester**: Test webpage iframe compatibility and embeddability
- **Embed Code Generator**: Generate standard iframe embed code
- **Multi-Platform Extractors**: Support for 6 gaming platforms (Itch.io, AzGames, ArmorGames, Miniplay, CrazyGames, Y8)
- **Organized Tool Categories**: General development tools and platform-specific extractors

#### 3. Data Management
- **View Data**: Display scraped game information in table format
- **Smart Deduplication**: Automatically detect and skip duplicate games
- **Data Export**: Support JSON/CSV formats with full/incremental export
- **Data Statistics**: Show detailed statistics of successful scraping and skipped duplicates

#### 4. Prompt Export
- **Template System**: Built-in multiple prompt templates (standard, concise, detailed, etc.)
- **Incremental Export**: Export only games added in the last 24 hours
- **Full Export**: Export all historical scraped data
- **Formatted Output**: Generate structured TXT files for further processing

#### 5. Manual Fetch
- Support for inputting single game page URLs
- Quick iframe address extraction
- One-click copy of formatted results
- Support for multiple platform URL parsing

### Scraping Process
1. Access gaming platform list pages
2. Intelligently extract game links and names
3. Visit individual game detail pages
4. Multi-strategy parsing and iframe address extraction
5. Deduplication check and save to local database



## Data Format

Scraped game data contains the following fields:
```json
{
  "name": "Game Name",
  "url": "Game Page URL",
  "embed_url": "Embed Game Address",
  "iframe_url": "Iframe Game Address",
  "platform": "Platform Name",
  "scraped_at": "Scraping Timestamp"
}
```

### Export Formats

#### JSON Export Example
```json
[
  {
    "name": "Example Game",
    "url": "https://example.com/game",
    "embed_url": "https://example.com/game.embed",
    "iframe_url": "https://example.com/embed/game",
    "platform": "platform.io",
    "scraped_at": "2025-09-20 10:30:00"
  }
]
```

#### Prompt Export Example
```
# GameScout Prompt Export - New Data
# Export Time: 2025-09-20 10:30:00
# Game Count: 5

1. Learn demo.php and development guide.md, then strictly follow demo.php and development guide.md to help me develop the following game page:
Game Name: Example Game
FAQ and info reference: https://example.com/game
<iframe> embed link: https://example.com/embed/game

2. ...
```

## Build EXE

```bash
python build.py
```

The packaged file will be located at `dist/GameScout.exe`

## Project Structure

```
GameScout/
├── main.py                    # Main program entry, GUI interface
├── build.py                   # Build script
├── requirements.txt           # Dependencies list
├── logo.ico                   # Program icon
├── modules/                   # Feature modules
│   ├── __init__.py
│   ├── port_detector.py       # Port detection module
│   ├── game_scraper.py        # Generic game scraper base class
│   ├── azgames_scraper.py     # AzGames platform scraper
│   └── data_manager.py        # Data management module
├── data/                      # Data storage directory
│   ├── games.json             # JSON data file
│   └── games.db               # SQLite database
├── dist/                      # Build output directory
│   ├── GameScout.exe          # Standalone executable
│   └── data/                  # Data directory
├── venv/                      # Virtual environment
├── README.md                  # English documentation
└── README_CN.md               # Chinese documentation
```

## Technical Features

### Intelligent Scraping Strategy
- **Multi-tier Fallback**: Automatic switching from requests → Selenium
- **Anti-bot Handling**: Smart User-Agent rotation and delay control
- **Error Recovery**: Automatic retry on network exceptions, resume from breakpoint
- **Resource Optimization**: Memory management and process pool control

### Data Security
- **Dual Storage**: JSON + SQLite dual backup
- **Transaction Processing**: Ensure data consistency
- **Deduplication Algorithm**: Intelligent duplicate data detection
- **Incremental Updates**: Process only new data for improved efficiency



## Important Notes

1. **Browser Requirements**: Chrome browser required for Selenium automation
2. **Network Environment**: Stable internet connection needed to access target platforms
3. **Scraping Frequency**: Built-in intelligent delay mechanism to avoid server pressure
4. **Data Backup**: Regularly backup important data in the data directory
5. **Compliance**: Please follow target websites' robots.txt and terms of service

## FAQ

### Q: EXE file won't run?
A: Check if Windows Defender or antivirus software is blocking it; add to trusted list

### Q: Chrome WebDriver error?
A: Ensure Chrome browser is installed; the program will automatically download matching WebDriver

### Q: What to do if scraping is interrupted?
A: The program supports resume from breakpoint; restart scraping to continue from where it left off

### Q: Data export failed?
A: Check data directory permissions; ensure the program has read/write access

### Q: Manual fetch feature not responding?
A: Check if the input URL format is correct and ensure network connection is stable



## Development Guide

### Adding New Platform Support
1. Inherit from `GameScraper` base class to create new scraper
2. Implement `scrape_games_list()` and `scrape_game_detail()` methods
3. Add corresponding GUI tab in `main.py`
4. Update data manager to support new platform

### Custom Prompt Templates
1. Modify `prompt_templates` dictionary in `main.py`
2. Add new template variables and formatting rules
3. Update `generate_prompts()` method to support new fields

### Extending Export Features
1. Add new export formats in `data_manager.py`
2. Modify `export_games()` method to support new formats
3. Update GUI interface to add new export options

## Technical Architecture

### Core Modules
- **GameScraper**: Scraper base class defining common interfaces
- **DataManager**: Data manager handling storage and export
- **PortDetector**: Port detector automatically finding available ports
- **GUI**: Modern interface based on Tkinter

### Design Patterns
- **Strategy Pattern**: Different platforms use different scraping strategies
- **Factory Pattern**: Dynamic creation of scraper instances
- **Observer Pattern**: GUI real-time updates of scraping status
- **Singleton Pattern**: Data manager ensures data consistency

## License

This project is for learning and research purposes only. Please comply with relevant website terms of service and legal regulations.

## Changelog

### v2.2.0 (2025-09-21)
- ✨ Added comprehensive game development toolkit with 8 specialized tools
- ✨ New "Tools" tab with direct browser access to iframe extraction tools
- ✨ Support for 6 gaming platforms: Itch.io, AzGames, ArmorGames, Miniplay, CrazyGames, Y8
- ✨ Integrated iframe compatibility tester and embed code generator
- 🎨 Enhanced UI with organized tool categories and improved navigation
- 📝 Updated manual fetch feature with expanded platform support information

### v2.1.0 (2025-09-20)
- 🔧 Fixed duplicate `/index.html/index.html` URL issues
- 🔧 Improved WebDriver resource management
- 📝 Comprehensive bilingual documentation

### v2.0.0 (2025-09-20)
- ✨ Added multi-platform support (2 gaming platforms)
- ✨ Smart deduplication to avoid duplicate data
- ✨ Prompt template export with incremental/full export options
- ✨ Manual fetch feature for single URL processing
- 🎨 Brand new unified GUI design
- 🔧 Optimized scraping strategies for higher success rates

---

## Author

**Prompt2Tool** - [prompt2tool.com](https://prompt2tool.com)

Focused on AI tool development and automation solutions