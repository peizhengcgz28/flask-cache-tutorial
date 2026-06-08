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
        # 强制刷新数据库连接，避免使用已断开的旧连接
        db.db.connection = None
        db.reset()
        cache.clear()
        current_app.extensions.get('cache_keys', set()).clear()
        return api_response({'message': '数据库已重置，所有数据已清空'})
    except Exception as e:
        print(f"[reinit-db] 错误: {e}")
        traceback.print_exc()
        return api_response(None, f"重置失败: {e}", 500)
