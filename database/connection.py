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
