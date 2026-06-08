"""统计业务逻辑"""


def build_stats_response(db, cache_config: dict, rate_limits: dict) -> dict:
    statistics = db.get_statistics()
    return {
        'statistics': statistics,
        'cache_config': cache_config,
        'rate_limits': rate_limits,
    }
