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
