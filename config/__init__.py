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
