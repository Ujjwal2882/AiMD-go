import redis
from app.core.config import settings

def get_redis_client():
    """Returns a Redis client instance."""
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return client

redis_client = get_redis_client()
