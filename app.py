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
