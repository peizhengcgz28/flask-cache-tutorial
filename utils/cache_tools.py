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
