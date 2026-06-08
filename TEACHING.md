# Flask 缓存与限流项目 — 教学步骤

本文档将本项目从零到一的完整源码按 8 个步骤拆解，每步包含教学目标、完整代码和原理说明。

---

## 第一步：项目骨架与配置层

### 目标
搭建目录结构，完成配置管理。

### 项目目录结构

```
flask-cache-tutorial/
├── app.py                    # 入口
├── .env                      # 环境变量
├── requirements.txt          # 依赖
├── config/                   # 配置层
│   └── __init__.py
├── core/                     # 核心层
│   └── __init__.py
├── database/                 # 数据库层
│   ├── __init__.py
│   ├── connection.py
│   └── queries.py
├── service/                  # 业务逻辑层
│   ├── __init__.py
│   └── stats_service.py
├── api/                      # API 接口层
│   ├── __init__.py
│   ├── system.py
│   └── users.py
├── utils/                    # 工具层
│   ├── __init__.py
│   ├── response.py
│   └── cache_tools.py
└── templates/
    └── index.html
```

### 完整源码

**.env**

```python
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=flask_cache_tutorial
SECRET_KEY=teaching-secret-key-2024
```

**requirements.txt**

```
Flask>=2.0,<4.0
Flask-Caching>=1.10
Flask-Limiter>=2.0
mysql-connector-python>=8.0
python-dotenv>=0.20
```

**config/\_\_init\_\_.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'teaching-secret-key-2024')

    DB_CONFIG: dict = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '3306')),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', 'root'),
        'database': os.getenv('DB_NAME', 'flask_cache_tutorial'),
        'charset': 'utf8mb4',
    }

    CACHE_TYPE: str = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT: int = 60
    CACHE_THRESHOLD: int = 100

    RATELIMIT_ENABLED: bool = True
    RATELIMIT_DEFAULT: str = "100/hour;10/minute"

    API_RATE_LIMITS: dict = {
        'users': "60/hour",
        'slow': "5/minute",
        'search': "30/minute",
    }
```

### 教学要点

| 概念 | 说明 |
|---|---|
| 12-Factor App | 配置与代码分离，通过环境变量注入 |
| `python-dotenv` | 自动加载 `.env` 文件中的环境变量 |
| 类管理配置 | 比散落全局变量更易维护和继承 |
| DB_CONFIG | 统一管理数据库连接参数 |

---

## 第二步：核心层 — 扩展单例

### 目标

实例化 Flask-Caching 和 Flask-Limiter 的单例对象，供全局复用。

### 完整源码

**core/\_\_init\_\_.py**

```python
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

cache: Cache = Cache()
limiter: Limiter = Limiter(get_remote_address)
```

### 教学要点

| 概念 | 说明 |
|---|---|
| 延迟初始化 | 先创建实例，`init_app(app)` 在工厂中绑定具体应用 |
| 单例模式 | 所有模块共享同一个 cache / limiter 实例 |
| `get_remote_address` | 限流默认以客户端 IP 为标识 |
| 内存存储 | 限流默认使用内存，适合教学演示 |

---

## 第三步：数据库层（上）— 连接管理与自动建库建表

### 目标

实现无需手动 SQL 脚本即可自动创建库和表。

### 完整源码

**database/\_\_init\_\_.py**

```python
from database.connection import Database
```

**database/connection.py**

```python
from typing import Optional
import mysql.connector
from mysql.connector import Error
from config import Config


class Database:
    """数据库连接管理 + 自动初始化"""

    def __init__(self) -> None:
        self.config: dict = Config.DB_CONFIG
        self.connection: Optional[mysql.connector.MySQLConnection] = None

    def _connect(self, db_name: Optional[str] = None) -> Optional[mysql.connector.MySQLConnection]:
        cfg = {k: v for k, v in self.config.items() if k != 'database'}
        if db_name:
            cfg['database'] = db_name
        try:
            return mysql.connector.connect(**cfg)
        except Error as e:
            print(f"[DB] 连接失败: {e}")
            return None

    def get_connection(self) -> Optional[mysql.connector.MySQLConnection]:
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connection = self._connect(self.config['database'])
            return self.connection
        except Error as e:
            print(f"[DB] 获取连接失败: {e}")
            return None

    def _ensure_database(self) -> bool:
        conn = self._connect(db_name=None)
        if not conn:
            return False
        try:
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.config['database']}` "
                           f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
            return True
        except Error as e:
            print(f"[DB] 创建数据库失败: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    def _ensure_tables(self) -> None:
        conn = self.get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `users` (
                    `id` INT PRIMARY KEY AUTO_INCREMENT,
                    `username` VARCHAR(50) UNIQUE NOT NULL,
                    `email` VARCHAR(100) UNIQUE NOT NULL,
                    `full_name` VARCHAR(100),
                    `is_active` BOOLEAN DEFAULT TRUE,
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `access_logs` (
                    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
                    `ip_address` VARCHAR(45) NOT NULL,
                    `request_path` VARCHAR(500) NOT NULL,
                    `status_code` INT NOT NULL,
                    `response_time_ms` INT NOT NULL,
                    `cache_hit` BOOLEAN DEFAULT FALSE,
                    `rate_limit_hit` BOOLEAN DEFAULT FALSE,
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX `idx_ip` (`ip_address`),
                    INDEX `idx_created_at` (`created_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `cache_logs` (
                    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
                    `cache_key` VARCHAR(500) NOT NULL,
                    `hit` BOOLEAN DEFAULT FALSE,
                    `endpoint` VARCHAR(200),
                    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX `idx_hit` (`hit`),
                    INDEX `idx_created_at` (`created_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
        except Error as e:
            print(f"[DB] 建表失败: {e}")
            conn.rollback()
        finally:
            cursor.close()

    def _seed_data(self) -> None:
        conn = self.get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM `users`")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT IGNORE INTO `users` (`username`, `email`, `full_name`) VALUES
                    ('admin', 'admin@example.com', '系统管理员'),
                    ('alice', 'alice@example.com', 'Alice Johnson'),
                    ('bob', 'bob@example.com', 'Bob Smith'),
                    ('charlie', 'charlie@example.com', 'Charlie Brown'),
                    ('diana', 'diana@example.com', 'Diana Prince')
                """)
                conn.commit()
        except Error as e:
            print(f"[DB] 种子数据失败: {e}")
        finally:
            cursor.close()

    def init_database(self) -> None:
        if self._ensure_database():
            self._ensure_tables()
            self._seed_data()

    def reset(self) -> None:
        conn = self.get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute("DROP TABLE IF EXISTS `cache_logs`")
            cursor.execute("DROP TABLE IF EXISTS `access_logs`")
            cursor.execute("DROP TABLE IF EXISTS `users`")
            conn.commit()
        except Error as e:
            print(f"[DB] 重置失败: {e}")
            conn.rollback()
        finally:
            cursor.close()
        self._ensure_tables()
        self._seed_data()
```

### 教学要点

| 概念 | 说明 |
|---|---|
| `CREATE DATABASE IF NOT EXISTS` | 幂等建库，重复运行不报错 |
| `CREATE TABLE IF NOT EXISTS` | 幂等建表，方便教学调试 |
| `INSERT IGNORE` | 种子数据只插入一次，不重复污染 |
| `DROP TABLE IF EXISTS` | 安全重置表 |
| 连接管理 | `get_connection()` 统一入口，支持断线重连 |
| `utf8mb4` | 支持完整 Unicode（含 emoji） |

---

## 第四步：数据库层（下）— 查询、日志与统计

### 目标

提供完整的 CRUD、访问日志、缓存日志和统计查询。

### 完整源码

**database/queries.py**

```python
from __future__ import annotations
from typing import Any, Optional
from mysql.connector import Error
from database import Database


class Queries:
    """数据查询层：CRUD + 日志 + 统计"""

    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _fmt_rows(rows: list[dict]) -> list[dict]:
        for row in rows:
            for k, v in row.items():
                if hasattr(v, 'strftime'):
                    row[k] = v.strftime('%Y-%m-%d %H:%M:%S')
        return rows

    # ── 用户 ──

    def get_all_users(self) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        if not conn:
            return []
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM `users` ORDER BY `id`")
            return self._fmt_rows(cursor.fetchall())
        except Error as e:
            print(f"[Q] 查询用户失败: {e}")
            return []
        finally:
            cursor.close()

    def get_user_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        conn = self.db.get_connection()
        if not conn:
            return None
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM `users` WHERE `id` = %s", (user_id,))
            row = cursor.fetchone()
            return self._fmt_rows([row])[0] if row else None
        except Error as e:
            print(f"[Q] 查询用户失败: {e}")
            return None
        finally:
            cursor.close()

    def search_users(self, keyword: str) -> list[dict[str, Any]]:
        conn = self.db.get_connection()
        if not conn:
            return []
        cursor = conn.cursor(dictionary=True)
        try:
            like = f"%{keyword}%"
            cursor.execute(
                "SELECT * FROM `users` WHERE `username` LIKE %s "
                "OR `email` LIKE %s OR `full_name` LIKE %s LIMIT 50",
                (like, like, like),
            )
            return self._fmt_rows(cursor.fetchall())
        except Error as e:
            print(f"[Q] 搜索失败: {e}")
            return []
        finally:
            cursor.close()

    # ── 日志 ──

    def log_access(self, ip_address: str, request_path: str, status_code: int,
                   response_time: int, cache_hit: bool = False, rate_hit: bool = False) -> None:
        conn = self.db.get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO `access_logs` (`ip_address`,`request_path`,`status_code`,"
                "`response_time_ms`,`cache_hit`,`rate_limit_hit`) VALUES (%s,%s,%s,%s,%s,%s)",
                (ip_address, request_path, status_code, response_time, cache_hit, rate_hit),
            )
            conn.commit()
        except Error as e:
            print(f"[Q] 日志失败: {e}")
        finally:
            cursor.close()

    def log_cache(self, cache_key: str, endpoint: str, hit: bool = True) -> None:
        conn = self.db.get_connection()
        if not conn:
            return
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO `cache_logs` (`cache_key`, `hit`, `endpoint`) VALUES (%s,%s,%s)",
                (cache_key, hit, endpoint),
            )
            conn.commit()
        except Error as e:
            print(f"[Q] 缓存日志失败: {e}")
        finally:
            cursor.close()

    # ── 维护 ──

    def reset(self) -> None:
        self.db.reset()

    # ── 统计 ──

    def get_statistics(self) -> dict[str, Any]:
        conn = self.db.get_connection()
        if not conn:
            return {}
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM `access_logs`")
            total = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM `cache_logs`")
            total_c = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM `cache_logs` WHERE `hit` = TRUE")
            hits = cursor.fetchone()[0] or 0
            rate = (hits / total_c * 100) if total_c > 0 else 0.0

            cursor.execute("SELECT COUNT(*) FROM `access_logs` WHERE `rate_limit_hit` = TRUE")
            limit_hits = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM `users`")
            users = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COALESCE(AVG(`response_time_ms`),0) FROM `access_logs`")
            avg = cursor.fetchone()[0] or 0.0

            return {
                'total_access': total,
                'cache_hit_rate': round(rate, 2),
                'rate_limit_hits': limit_hits,
                'user_count': users,
                'avg_response_time': round(float(avg), 2),
            }
        except Error as e:
            print(f"[Q] 统计失败: {e}")
            return {}
        finally:
            cursor.close()
```

### 教学要点

| 概念 | 说明 |
|---|---|
| `dictionary=True` | 游标以字典形式返回结果，键为字段名 |
| `%s` 占位符 | 参数化查询，防止 SQL 注入 |
| `LIKE` 模糊搜索 | 结合 `%keyword%` 实现多字段搜索 |
| `COALESCE` | 聚合查询中处理 NULL 值 |
| `strftime` | 将 MySQL datetime 格式化为可读字符串 |

---

## 第五步：工具层 — 响应格式与装饰器

### 目标

封装统一的 JSON 响应格式、缓存和计时装饰器。

### 完整源码

**utils/\_\_init\_\_.py** — 空文件

**utils/response.py**

```python
import json
import datetime
from typing import Any
from functools import wraps

from flask import jsonify, Response


def timestamp() -> str:
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def api_response(data: Any = None, message: str = "success", status: int = 200) -> tuple:
    body = {'success': status == 200, 'message': message, 'data': data, 'timestamp': timestamp()}
    return jsonify(body), status


def fix_json_response(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        result = f(*args, **kwargs)
        if isinstance(result, tuple) and len(result) == 2:
            response, status_code = result
            data = response.get_json() if hasattr(response, 'get_json') else response
            return Response(json.dumps(data, ensure_ascii=False),
                            status=status_code,
                            mimetype='application/json; charset=utf-8')
        return result
    return wrapper
```

**utils/cache_tools.py**

```python
import hashlib
import time
from functools import wraps
from typing import Optional

from flask import request, jsonify, Response
from flask_caching import Cache

from utils.response import timestamp


def make_cache_key() -> str:
    raw = f"{request.path}:{sorted(request.args.items())}"
    return hashlib.md5(raw.encode()).hexdigest()


def cache_response(timeout: int = 60, cache: Optional[Cache] = None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            db = _get_db()
            key = make_cache_key()

            cached = cache.get(key) if cache else None
            if cached is not None:
                db.log_cache(key, request.path, hit=True)
                cached['from_cache'] = True
                cached['cached_at'] = timestamp()
                resp = jsonify(cached)
                resp.headers['X-Cache'] = 'HIT'
                resp.content_type = 'application/json; charset=utf-8'
                return resp

            result = f(*args, **kwargs)
            data = _extract(result)
            if data is not None and cache:
                cache.set(key, data, timeout=timeout)
                from flask import current_app
                current_app.extensions.setdefault('cache_keys', set()).add(key)

            db.log_cache(key, request.path, hit=False)

            if isinstance(result, tuple):
                result[0].headers['X-Cache'] = 'MISS'
            else:
                result.headers['X-Cache'] = 'MISS'
            return result
        return wrapper
    return decorator


def measure_time(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start = time.time() * 1000
        result = f(*args, **kwargs)
        elapsed = int(time.time() * 1000 - start)
        db = _get_db()
        db.log_access(
            ip_address=request.remote_addr or '',
            request_path=request.path,
            status_code=200,
            response_time=elapsed,
        )
        return result
    return wrapper


def _get_db():
    from flask import current_app
    return current_app.extensions['db']


def _extract(result):
    if isinstance(result, tuple):
        obj = result[0]
    else:
        obj = result
    if hasattr(obj, 'get_json'):
        return obj.get_json()
    return obj
```

### 教学要点

| 概念 | 说明 |
|---|---|
| 统一响应格式 | 所有接口返回 `{success, message, data, timestamp}` |
| 装饰器模式 | `@cache_response` 和 `@measure_time` 拦截函数调用 |
| `@wraps(f)` | 保留原函数的 `__name__`、`__doc__` 等元信息 |
| `X-Cache` 头 | HTTP 响应头传递缓存命中状态 |
| MD5 缓存键 | 将 URL + 查询参数哈希为定长键 |
| `from_cache` | 响应体中标记缓存命中，前端可直接读取 |
| `cache_keys` 集合 | 跟踪所有缓存键，用于 `/current-cache` 查询 |

---

## 第六步：业务逻辑层

### 目标

将统计拼装等业务逻辑抽离为独立服务，保持路由层简洁。

### 完整源码

**service/\_\_init\_\_.py** — 空文件

**service/stats_service.py**

```python
"""统计业务逻辑"""


def build_stats_response(db, cache_config: dict, rate_limits: dict) -> dict:
    statistics = db.get_statistics()
    return {
        'statistics': statistics,
        'cache_config': cache_config,
        'rate_limits': rate_limits,
    }
```

### 教学要点

| 概念 | 说明 |
|---|---|
| 分层架构 | api（controller）→ service → database（repository）|
| 单一职责 | 路由只负责 HTTP 处理，业务放在 service 层 |
| 可测试性 | service 层不依赖 Flask 上下文，可独立单元测试 |

---

## 第七步：API 接口层 — 路由与错误处理

### 目标

定义系统管理和用户 API 路由，叠加装饰器实现缓存、限流和错误处理。

### 完整源码

**api/\_\_init\_\_.py**

```python
from flask import Flask


def register_api_blueprints(app: Flask) -> None:
    from api.system import system_bp
    from api.users import users_bp
    app.register_blueprint(system_bp)
    app.register_blueprint(users_bp)
```

**api/system.py**

```python
from flask import Blueprint, render_template

from core import cache, limiter
from utils.response import api_response, fix_json_response
from service.stats_service import build_stats_response

system_bp = Blueprint('system', __name__)


@system_bp.route('/')
@limiter.exempt
def index():
    return render_template('index.html')


@system_bp.route('/stats')
@limiter.exempt
@fix_json_response
def get_stats():
    from flask import current_app
    db = current_app.extensions['db']
    cfg = {
        'type': current_app.config.get('CACHE_TYPE', 'SimpleCache'),
        'default_timeout': current_app.config.get('CACHE_DEFAULT_TIMEOUT', 60),
    }
    return api_response(build_stats_response(db, cfg, current_app.config.get('API_RATE_LIMITS', {})))


@system_bp.route('/current-cache')
@limiter.exempt
@fix_json_response
def current_cache():
    from flask import current_app
    tracked = current_app.extensions.get('cache_keys', set())
    valid = [k for k in tracked if cache.get(k) is not None]
    return api_response({'cache_keys': valid or '（无有效缓存）'})


@system_bp.route('/clear-cache')
@limiter.exempt
@fix_json_response
def clear_cache():
    cache.clear()
    from flask import current_app
    current_app.extensions.get('cache_keys', set()).clear()
    return api_response({'message': '所有缓存已清除'})


@system_bp.route('/reinit-db')
@limiter.exempt
@fix_json_response
def reinit_database():
    from flask import current_app
    import traceback
    try:
        db = current_app.extensions['db']
        db.db.connection = None
        db.reset()
        cache.clear()
        current_app.extensions.get('cache_keys', set()).clear()
        return api_response({'message': '数据库已重置，所有数据已清空'})
    except Exception as e:
        print(f"[reinit-db] 错误: {e}")
        traceback.print_exc()
        return api_response(None, f"重置失败: {e}", 500)
```

**api/users.py**

```python
import time

from flask import Blueprint, request

from config import Config
from core import cache, limiter
from utils.cache_tools import cache_response, measure_time
from utils.response import api_response, fix_json_response

users_bp = Blueprint('api', __name__)
limits = Config.API_RATE_LIMITS


def _db():
    from flask import current_app
    return current_app.extensions['db']


@users_bp.route('/users')
@cache_response(timeout=60, cache=cache)
@measure_time
@limiter.limit(limits['users'])
@fix_json_response
def get_users():
    return api_response(_db().get_all_users())


@users_bp.route('/user/<int:user_id>')
@cache_response(timeout=60, cache=cache)
@measure_time
@limiter.limit(limits['users'])
@fix_json_response
def get_user(user_id: int):
    user = _db().get_user_by_id(user_id)
    if user:
        return api_response(user)
    return api_response(None, "用户不存在", 404)


@users_bp.route('/search')
@cache_response(timeout=30, cache=cache)
@measure_time
@limiter.limit(limits['search'])
@fix_json_response
def search_users():
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return api_response(None, "请输入搜索关键词", 400)
    users = _db().search_users(keyword)
    return api_response({'keyword': keyword, 'results': users, 'count': len(users)})


@users_bp.route('/slow')
@measure_time
@limiter.limit(limits['slow'])
@fix_json_response
def slow_endpoint():
    time.sleep(2)
    return api_response({'message': '慢速接口（2秒延迟），严格限流保护中', 'execution_time': '2秒'})


# ── 错误处理 ──

@users_bp.errorhandler(429)
@fix_json_response
def ratelimit_error(e):
    _db().log_access(
        ip_address=request.remote_addr or '',
        request_path=request.path,
        status_code=429,
        response_time=0,
        rate_hit=True,
    )
    return api_response(None, f"请求过于频繁，请稍后再试（限制: {e.description}）", 429)


@users_bp.errorhandler(404)
@fix_json_response
def not_found(e):
    return api_response(None, "请求的资源不存在", 404)


@users_bp.errorhandler(500)
@fix_json_response
def internal_error(e):
    return api_response(None, "服务器内部错误", 500)
```

### 教学要点

| 概念 | 说明 |
|---|---|
| Blueprint | 按功能域拆分路由 |
| `@limiter.exempt` | 系统管理接口免除限流 |
| `@limiter.limit("5/minute")` | 细粒度限流规则 |
| `errorhandler(429)` | 自定义限流触发响应 |
| `errorhandler(500)` | 全局服务器错误捕获 |

### 装饰器执行顺序

```
请求到达
  │
  ├─ cache_response     → 检查缓存 → HIT 直接返回
  │                        MISS 继续往下
  ├─ measure_time       → 记录响应时间
  ├─ limiter.limit      → 检查限流 → 超限抛 429
  ├─ fix_json_response  → 确保 UTF-8 编码
  └─ get_users()        → 实际业务逻辑
```

---

## 第八步：入口与前端

### 目标

工厂函数组装所有模块；交互式前端仪表板展示缓存和限流效果。

### 完整源码

**app.py**

```python
from flask import Flask
from config import Config
from core import cache, limiter
from api import register_api_blueprints


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    from database import Database
    from database.queries import Queries
    db = Database()
    db.init_database()
    app.extensions['db'] = Queries(db)
    app.extensions['cache_keys'] = set()

    cache.init_app(app)
    limiter.init_app(app)

    register_api_blueprints(app)
    return app


if __name__ == '__main__':
    app = create_app()
    print("=" * 50)
    print("  Flask 缓存与限流教学项目")
    print("=" * 50)
    print("  访问 http://localhost:5000/")
    app.run(debug=True, host='0.0.0.0', port=5000)
```

**templates/index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flask 缓存与限流教学演示</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font: 15px/1.6 -apple-system, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; }
  .container { max-width: 1100px; margin: 0 auto; padding: 24px 20px; }

  .header { background: linear-gradient(135deg, #1a1a2e, #16213e); color: #fff; padding: 32px 0; text-align: center; }
  .header h1 { font-size: 26px; letter-spacing: 1px; }
  .header p { opacity: .75; margin-top: 6px; font-size: 14px; }

  .tabs { display: flex; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 24px; }
  .tabs button { flex: 1; padding: 14px 8px; border: none; background: transparent; cursor: pointer; font-size: 14px; font-weight: 600; color: #666; transition: .2s; }
  .tabs button:hover { background: #f5f5f5; }
  .tabs button.active { color: #1a73e8; background: #e8f0fe; }
  .tabs button.active::after { content: ''; position: absolute; bottom: 0; left: 20%; right: 20%; height: 3px; background: #1a73e8; border-radius: 3px 3px 0 0; }

  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .card { background: #fff; border-radius: 10px; box-shadow: 0 1px 6px rgba(0,0,0,.06); padding: 24px; margin-bottom: 20px; }
  .card h3 { font-size: 16px; color: #1a1a2e; margin-bottom: 14px; }

  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
  .badge-hit { background: #e6f4ea; color: #1e7e34; }
  .badge-miss { background: #fce8e6; color: #c5221f; }
  .badge-limit { background: #fff3cd; color: #856404; }
  .badge-ok { background: #d4edda; color: #155724; }

  .btn { display: inline-block; padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; transition: .2s; }
  .btn-primary { background: #1a73e8; color: #fff; }
  .btn-primary:hover { background: #1557b0; }
  .btn-danger { background: #dc3545; color: #fff; }
  .btn-danger:hover { background: #b02a37; }
  .btn-outline { background: transparent; border: 1.5px solid #1a73e8; color: #1a73e8; }
  .btn-outline:hover { background: #e8f0fe; }
  .btn-sm { padding: 5px 14px; font-size: 13px; }

  .flex-row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .input { padding: 8px 12px; border: 1.5px solid #ddd; border-radius: 6px; font-size: 14px; width: 200px; outline: none; }
  .input:focus { border-color: #1a73e8; }

  .result-box { background: #f8f9fa; border-radius: 8px; padding: 16px; margin-top: 14px; font-family: 'SF Mono', monospace; font-size: 13px; max-height: 320px; overflow: auto; white-space: pre-wrap; border: 1px solid #e9ecef; }

  .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; }
  .stat-item { text-align: center; padding: 16px 8px; background: #f8f9fa; border-radius: 8px; }
  .stat-item .num { font-size: 28px; font-weight: 700; color: #1a73e8; }
  .stat-item .label { font-size: 12px; color: #666; margin-top: 4px; }

  .cache-visual { display: flex; gap: 8px; align-items: center; margin-top: 12px; }
  .cache-dot { width: 14px; height: 14px; border-radius: 50%; display: inline-block; }
  .cache-dot.hit { background: #34a853; box-shadow: 0 0 6px rgba(52,168,83,.5); }
  .cache-dot.miss { background: #ea4335; box-shadow: 0 0 6px rgba(234,67,53,.5); }

  .history-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  .history-item { padding: 4px 12px; border-radius: 14px; font-size: 12px; font-weight: 600; }
  .history-item.hit { background: #e6f4ea; color: #1e7e34; border: 1px solid #a8dab5; }
  .history-item.miss { background: #fce8e6; color: #c5221f; border: 1px solid #f5c6cb; }

  .progress-bar { height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden; margin-top: 6px; }
  .progress-bar .fill { height: 100%; background: linear-gradient(90deg, #34a853, #1a73e8); border-radius: 4px; transition: width .4s; }

  .rate-status { padding: 12px 16px; border-radius: 8px; margin-top: 12px; font-weight: 600; }
  .rate-ok { background: #e6f4ea; color: #155724; border-left: 4px solid #34a853; }
  .rate-block { background: #fce8e6; color: #721c24; border-left: 4px solid #dc3545; }

  @media (max-width: 600px) {
    .tabs button { font-size: 12px; padding: 10px 4px; }
    .stat-grid { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>

<div class="header">
  <div class="container">
    <h1>Flask 缓存与限流教学演示</h1>
    <p>交互式体验 · 缓存命中可视化 · 限流实时反馈</p>
  </div>
</div>

<div class="container">

  <div class="tabs">
    <button class="active" data-tab="overview">概览</button>
    <button data-tab="cache">缓存演示</button>
    <button data-tab="ratelimit">限流演示</button>
    <button data-tab="stats">统计</button>
  </div>

  <!-- 概览 -->
  <div class="tab-content active" id="tab-overview">
    <div class="card">
      <h3>项目介绍</h3>
      <p>本项目演示 <strong>Flask-Caching</strong> 和 <strong>Flask-Limiter</strong> 两大扩展的核心用法。</p>
      <ul style="margin-top:10px;padding-left:20px">
        <li><strong>缓存技术</strong> — 减少重复计算和数据库查询，提升响应速度</li>
        <li><strong>限流技术</strong> — 防止接口被恶意刷请求，保护后端资源</li>
      </ul>
    </div>
    <div class="card">
      <h3>API 端点速览</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <tr style="border-bottom:2px solid #eee">
          <th style="text-align:left;padding:8px 4px">端点</th>
          <th style="text-align:left;padding:8px 4px">说明</th>
          <th style="text-align:left;padding:8px 4px">缓存</th>
          <th style="text-align:left;padding:8px 4px">限流</th>
        </tr>
        <tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:8px 4px"><code>/users</code></td>
          <td>获取所有用户</td>
          <td><span class="badge badge-hit">60s</span></td>
          <td><span class="badge badge-ok">60/h</span></td>
        </tr>
        <tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:8px 4px"><code>/user/&lt;id&gt;</code></td>
          <td>获取单个用户</td>
          <td><span class="badge badge-hit">60s</span></td>
          <td><span class="badge badge-ok">60/h</span></td>
        </tr>
        <tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:8px 4px"><code>/search?q=</code></td>
          <td>搜索用户</td>
          <td><span class="badge badge-hit">30s</span></td>
          <td><span class="badge badge-ok">30/m</span></td>
        </tr>
        <tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:8px 4px"><code>/slow</code></td>
          <td>模拟慢接口（2s）</td>
          <td><span class="badge badge-miss">无</span></td>
          <td><span class="badge badge-limit">5/m</span></td>
        </tr>
        <tr>
          <td style="padding:8px 4px"><code>/stats</code></td>
          <td>系统统计</td>
          <td><span class="badge badge-miss">无</span></td>
          <td><span class="badge badge-ok">无</span></td>
        </tr>
      </table>
    </div>
    <div class="card">
      <h3>数据库管理</h3>
      <p style="margin-bottom:10px">重置数据库表结构和演示数据（清空统计、重建用户数据）。</p>
      <button class="btn btn-danger btn-sm" onclick="reinitDb()">重新初始化数据库</button>
      <div class="result-box" id="db-result" style="margin-top:12px"></div>
    </div>
  </div>

  <!-- 缓存演示 -->
  <div class="tab-content" id="tab-cache">
    <div class="card">
      <h3>缓存命中测试</h3>
      <p style="margin-bottom:10px">连续请求同一接口，观察 <span class="badge badge-hit">HIT</span> 与 <span class="badge badge-miss">MISS</span> 变化。</p>
      <div class="flex-row">
        <button class="btn btn-primary" id="btn-users">获取所有用户</button>
        <input class="input" id="input-user-id" type="number" min="1" max="5" value="1" placeholder="用户 ID">
        <button class="btn btn-primary" id="btn-user">获取单个用户</button>
      </div>
      <div style="margin-top:12px">
        <input class="input" id="input-search" placeholder="搜索关键词 (如 alice)">
        <button class="btn btn-primary" id="btn-search">搜索</button>
      </div>
      <div class="cache-visual" id="cache-visual">
        <span class="cache-dot" id="cache-dot"></span>
        <span id="cache-label">等待请求 ...</span>
      </div>
      <div class="result-box" id="cache-result">{ }</div>
      <div class="history-list" id="cache-history"></div>
    </div>
    <div class="card">
      <h3>缓存管理</h3>
      <div class="flex-row">
        <button class="btn btn-outline btn-sm" onclick="fetchCacheKeys()">查看当前缓存</button>
        <button class="btn btn-danger btn-sm" onclick="clearAllCache()">清除所有缓存</button>
      </div>
      <div class="result-box" id="cache-keys-result" style="margin-top:12px"></div>
    </div>
  </div>

  <!-- 限流演示 -->
  <div class="tab-content" id="tab-ratelimit">
    <div class="card">
      <h3>慢接口限流测试</h3>
      <p style="margin-bottom:10px">接口 <code>/slow</code> 限制 <strong>5 次 / 分钟</strong>。快速点击下方按钮，观察限流触发。</p>
      <button class="btn btn-danger" id="btn-slow">请求慢接口</button>
      <div class="rate-status" id="rate-status">等待请求 ...</div>
      <div class="result-box" id="slow-result">{ }</div>
    </div>
    <div class="card">
      <h3>请求时序</h3>
      <div class="history-list" id="slow-history"></div>
    </div>
  </div>

  <!-- 统计 -->
  <div class="tab-content" id="tab-stats">
    <div class="card">
      <h3>系统统计</h3>
      <button class="btn btn-primary" onclick="fetchStats()">刷新统计</button>
      <div class="stat-grid" id="stats-grid" style="margin-top:16px">
        <div class="stat-item"><div class="num" id="stat-total-access">0</div><div class="label">总访问次数</div></div>
        <div class="stat-item"><div class="num" id="stat-cache-rate">0%</div><div class="label">缓存命中率</div></div>
        <div class="stat-item"><div class="num" id="stat-rate-hits">0</div><div class="label">限流触发次数</div></div>
        <div class="stat-item"><div class="num" id="stat-users">0</div><div class="label">用户总数</div></div>
        <div class="stat-item"><div class="num" id="stat-avg-time">0ms</div><div class="label">平均响应时间</div></div>
      </div>
    </div>
    <div class="card">
      <h3>缓存命中率</h3>
      <div class="progress-bar" style="height:20px"><div class="fill" id="cache-rate-bar" style="width:0%"></div></div>
      <p style="margin-top:6px;font-size:13px;color:#666">命中率: <span id="cache-rate-text">0%</span></p>
    </div>
  </div>

</div>

<script>
document.querySelectorAll('.tabs button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tabs button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

async function apiCall(url) {
  const resp = await fetch(url);
  const text = await resp.text();
  let body;
  try { body = JSON.parse(text); } catch { body = {}; }
  const cacheStatus = body.from_cache ? 'HIT' : (resp.headers.get('X-Cache') || (body.data ? 'MISS' : '-'));
  return { status: resp.status, cacheHeader: cacheStatus, text };
}

function formatJSON(text) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; }
}

// ─── Cache Demo ──
let cacheHistory = [];

function updateCacheVisual(h) {
  const dot = document.getElementById('cache-dot');
  const label = document.getElementById('cache-label');
  if (h === 'HIT') {
    dot.className = 'cache-dot hit';
    label.textContent = ' 缓存命中 (HIT) - 数据来自缓存';
    label.style.color = '#1e7e34';
  } else if (h === 'MISS') {
    dot.className = 'cache-dot miss';
    label.textContent = ' 缓存未命中 (MISS) - 数据来自数据库';
    label.style.color = '#c5221f';
  } else {
    dot.className = 'cache-dot';
    label.textContent = '等待请求 ...';
    label.style.color = '#666';
  }
}

function addCacheHistory(type, status) {
  cacheHistory.unshift({ type, status, time: new Date().toLocaleTimeString() });
  if (cacheHistory.length > 20) cacheHistory.pop();
  document.getElementById('cache-history').innerHTML = cacheHistory.map(h =>
    `<span class="history-item ${h.status.toLowerCase()}">${h.type} . ${h.status} . ${h.time}</span>`
  ).join('');
}

async function fetchUsers() {
  const { status, cacheHeader, text } = await apiCall('/users');
  document.getElementById('cache-result').textContent = formatJSON(text);
  updateCacheVisual(cacheHeader);
  addCacheHistory('/users', cacheHeader || (status === 200 ? 'OK' : status));
}

async function fetchUser(id) {
  const { status, cacheHeader, text } = await apiCall(`/user/${id}`);
  document.getElementById('cache-result').textContent = formatJSON(text);
  updateCacheVisual(cacheHeader);
  addCacheHistory(`/user/${id}`, cacheHeader || (status === 200 ? 'OK' : status));
}

async function fetchSearch(q) {
  const { status, cacheHeader, text } = await apiCall(`/search?q=${encodeURIComponent(q)}`);
  document.getElementById('cache-result').textContent = formatJSON(text);
  updateCacheVisual(cacheHeader);
  addCacheHistory(`/search?q=${q}`, cacheHeader || (status === 200 ? 'OK' : status));
}

document.getElementById('btn-users').addEventListener('click', fetchUsers);
document.getElementById('btn-user').addEventListener('click', () => fetchUser(document.getElementById('input-user-id').value));
document.getElementById('btn-search').addEventListener('click', () => fetchSearch(document.getElementById('input-search').value));

async function fetchCacheKeys() {
  const { text } = await apiCall('/current-cache');
  document.getElementById('cache-keys-result').textContent = formatJSON(text);
}

async function clearAllCache() {
  const { text } = await apiCall('/clear-cache');
  document.getElementById('cache-keys-result').textContent = formatJSON(text);
  document.getElementById('cache-history').innerHTML = '';
  cacheHistory = [];
}

// ─── Rate Limit ──
let slowHistory = [];
let slowCount = 0;

async function fetchSlow() {
  slowCount++;
  const statusEl = document.getElementById('rate-status');
  const resultEl = document.getElementById('slow-result');
  const btn = document.getElementById('btn-slow');
  btn.disabled = true;
  btn.textContent = ' 请求中 ...';
  const start = Date.now();
  const { status, text } = await apiCall('/slow');
  const elapsed = Date.now() - start;
  if (status === 429) {
    statusEl.className = 'rate-status rate-block';
    statusEl.textContent = ` 第 ${slowCount} 次请求 - 限流触发！429 (${elapsed}ms)`;
  } else {
    statusEl.className = 'rate-status rate-ok';
    statusEl.textContent = ` 第 ${slowCount} 次请求 - 成功 (${elapsed}ms)`;
  }
  resultEl.textContent = formatJSON(text);
  slowHistory.unshift({ n: slowCount, status, time: new Date().toLocaleTimeString() });
  if (slowHistory.length > 20) slowHistory.pop();
  document.getElementById('slow-history').innerHTML = slowHistory.map(h =>
    `<span class="history-item ${h.status === 429 ? 'miss' : 'hit'}">#${h.n} ${h.status} . ${h.time}</span>`
  ).join('');
  btn.disabled = false;
  btn.textContent = '请求慢接口';
}

document.getElementById('btn-slow').addEventListener('click', fetchSlow);

// ─── Database ──
async function reinitDb() {
  const el = document.getElementById('db-result');
  el.textContent = ' 正在重新初始化数据库 ...';
  const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('请求超时')), 30000));
  try {
    const { status, text } = await Promise.race([apiCall('/reinit-db'), timeout]);
    el.textContent = `[${status}] ${formatJSON(text)}`;
    if (status === 200) setTimeout(fetchStats, 500);
  } catch (e) {
    el.textContent = ' 请求失败: ' + e.message;
  }
}

// ─── Stats ──
async function fetchStats() {
  const { text } = await apiCall('/stats');
  try {
    const d = JSON.parse(text);
    const s = d.data.statistics || {};
    document.getElementById('stat-total-access').textContent = s.total_access ?? 0;
    document.getElementById('stat-cache-rate').textContent = (s.cache_hit_rate ?? 0) + '%';
    document.getElementById('stat-rate-hits').textContent = s.rate_limit_hits ?? 0;
    document.getElementById('stat-users').textContent = s.user_count ?? 0;
    document.getElementById('stat-avg-time').textContent = (s.avg_response_time ?? 0) + 'ms';
    const rate = Math.min(s.cache_hit_rate ?? 0, 100);
    document.getElementById('cache-rate-bar').style.width = rate + '%';
    document.getElementById('cache-rate-text').textContent = rate + '%';
  } catch {}
}

document.querySelector('[data-tab="stats"]').addEventListener('click', fetchStats);
fetchStats();
</script>
</body>
</html>
```

### 教学要点

| 概念 | 说明 |
|---|---|
| 应用工厂 | `create_app()` 避免全局状态，便于测试 |
| `extensions` 字典 | 存储跨模块共享的实例 |
| `init_app()` | Flask 扩展的标准绑定模式 |
| `fetch` API | 浏览器原生 HTTP 请求 |
| `X-Cache` 头读取 | `resp.headers.get('X-Cache')` |
| DOM 操作 | 通过 `textContent` 更新界面 |

---

## 总览：请求全链路

```
浏览器 / 前端
    │  HTTP 请求
    ▼
Flask (app.py)
    │  路由分发
    ▼
Blueprint (api/users.py)
    │  @cache_response → 检查缓存
    │     ├─ 命中 → 返回缓存的 JSON + X-Cache: HIT
    │     └─ 未命中 → 继续
    │  @measure_time → 计时
    │  @limiter.limit → 检查限流
    │     ├─ 超限 → 429 Too Many Requests
    │     └─ 正常 → 继续
    ▼
Service (service/stats_service.py)
    │  业务逻辑组装
    ▼
Queries (database/queries.py)
    │  SQL 查询 / 日志写入
    ▼
Database (database/connection.py)
    │  连接管理
    ▼
MySQL 8.0
```

---

## 附录：数据表结构

### users（用户表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK AUTO_INCREMENT | 用户 ID |
| username | VARCHAR(50) UNIQUE | 用户名 |
| email | VARCHAR(100) UNIQUE | 邮箱 |
| full_name | VARCHAR(100) | 全名 |
| is_active | BOOLEAN DEFAULT TRUE | 是否激活 |
| created_at | TIMESTAMP | 创建时间 |

### access_logs（访问日志）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK AUTO_INCREMENT | 日志 ID |
| ip_address | VARCHAR(45) | 客户端 IP |
| request_path | VARCHAR(500) | 请求路径 |
| status_code | INT | HTTP 状态码 |
| response_time_ms | INT | 响应时间（毫秒） |
| cache_hit | BOOLEAN | 是否缓存命中 |
| rate_limit_hit | BOOLEAN | 是否限流触发 |
| created_at | TIMESTAMP | 记录时间 |

### cache_logs（缓存日志）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK AUTO_INCREMENT | 日志 ID |
| cache_key | VARCHAR(500) | 缓存键（MD5） |
| hit | BOOLEAN | 是否命中 |
| endpoint | VARCHAR(200) | 接口路径 |
| created_at | TIMESTAMP | 记录时间 |

---

## 扩展练习

1. **替换缓存后端**：将 `CACHE_TYPE` 改为 `RedisCache`，配置 Redis 地址
2. **替换限流存储**：将 `storage_uri` 改为 `redis://localhost:6379`
3. **添加认证限流**：基于 `Authorization` 头做用户级限流
4. **添加管理后台**：使用 Flask-Admin 实现用户 CRUD 可视化
5. **单元测试**：为 `Queries` 和 service 层编写 pytest 用例
6. **Docker 部署**：编写 `docker-compose.yml` 一键启动 Flask + MySQL
