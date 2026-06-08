from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

cache: Cache = Cache()
limiter: Limiter = Limiter(get_remote_address)
