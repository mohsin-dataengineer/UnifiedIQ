import pytest
from app.services.cache import CacheService


def test_set_and_get():
    cache = CacheService(maxsize=4, ttl=60)
    assert cache.get("missing") is None
    cache.set("k", {"v": 1})
    assert cache.get("k") == {"v": 1}


def test_per_key_ttl_override_rejected():
    cache = CacheService(maxsize=4, ttl=60)
    with pytest.raises(ValueError):
        cache.set("k", 1, ttl=5)
