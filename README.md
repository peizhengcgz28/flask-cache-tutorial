# Flask 缓存与限流教学项目

基于 Flask 3.x + MySQL 8.0 的交互式教学演示项目，直观展示缓存命中、限流触发等核心技术。

## 项目结构

```
├── app.py                    # 入口：工厂函数 + 启动
├── config/                   # 配置层
│   └── __init__.py           #   Config：数据库/缓存/限流参数
├── core/                     # 核心层
│   └── __init__.py           #   Cache + Limiter 单例
├── database/                 # 数据库层
│   ├── connection.py         #   连接管理 + 自动建库建表 + 重置
│   └── queries.py            #   CRUD + 日志记录 + 统计查询
├── service/                  # 业务逻辑层
│   └── stats_service.py      #   统计拼装
├── api/                      # API 接口层
│   ├── system.py             #   系统管理路由
│   └── users.py              #   用户路由 + 错误处理器
├── utils/                    # 工具层
│   ├── response.py           #   api_response + JSON 编码修复
│   └── cache_tools.py        #   缓存/计时装饰器 + 缓存键生成
└── templates/
    └── index.html            # 交互式前端仪表板
```

## 快速开始

### 环境要求

- Python 3.11+
- MySQL 8.0+

### 安装

```bash
# 1. 克隆 / 进入项目目录
cd flask-cache-tutorial

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量（可跳过，使用默认值）
#    编辑 .env 文件，按需修改数据库连接信息
```

### .env 配置说明

```
DB_HOST=localhost           # 数据库主机
DB_PORT=3306                # 端口
DB_USER=root                # 用户名
DB_PASSWORD=root            # 密码
DB_NAME=flask_cache_tutorial # 数据库名（自动创建）
```

### 启动

```bash
python app.py
```

首次启动会自动完成：

1. 连接到 MySQL
2. 创建数据库 `flask_cache_tutorial`（如不存在）
3. 创建 `users`、`access_logs`、`cache_logs` 三张表
4. 插入 5 条演示用户数据

访问 [http://localhost:5000](http://localhost:5000) 进入交互界面。

## API 端点

| 端点 | 说明 | 缓存 | 限流 |
|---|---|---|---|
| `/` | 首页 | 无 | 无 |
| `/users` | 获取所有用户 | 60s | 60 次/小时 |
| `/user/<id>` | 获取单个用户 | 60s | 60 次/小时 |
| `/search?q=` | 搜索用户 | 30s | 30 次/分钟 |
| `/slow` | 模拟慢接口（2s 延迟） | 无 | 5 次/分钟 |
| `/stats` | 系统统计 | 无 | 无 |
| `/current-cache` | 当前有效缓存键 | 无 | 无 |
| `/clear-cache` | 清除所有缓存 | 无 | 无 |
| `/reinit-db` | 重置数据库 | 无 | 无 |

## 技术栈

- **Flask** — Web 框架
- **Flask-Caching** — 缓存扩展（SimpleCache）
- **Flask-Limiter** — 限流扩展（内存存储）
- **MySQL 8.0 + mysql-connector-python** — 数据库
