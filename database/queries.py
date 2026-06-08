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
