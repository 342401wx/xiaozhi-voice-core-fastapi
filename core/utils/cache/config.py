"""
Cache configuration used by the extracted Xiaozhi core.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .strategies import CacheStrategy


class CacheType(Enum):
    LOCATION = "location"
    WEATHER = "weather"
    LUNAR = "lunar"
    INTENT = "intent"
    IP_INFO = "ip_info"
    CONFIG = "config"
    DEVICE_PROMPT = "device_prompt"
    VOICEPRINT_HEALTH = "voiceprint_health"
    AUDIO_DATA = "audio_data"


@dataclass
class CacheConfig:
    strategy: CacheStrategy = CacheStrategy.TTL
    ttl: Optional[float] = 300
    max_size: Optional[int] = 1000
    cleanup_interval: float = 60

    @classmethod
    def for_type(cls, cache_type: CacheType) -> "CacheConfig":
        configs = {
            CacheType.LOCATION: cls(strategy=CacheStrategy.TTL, ttl=None, max_size=1000),
            CacheType.IP_INFO: cls(strategy=CacheStrategy.TTL, ttl=86400, max_size=1000),
            CacheType.WEATHER: cls(strategy=CacheStrategy.TTL, ttl=28800, max_size=1000),
            CacheType.LUNAR: cls(strategy=CacheStrategy.TTL, ttl=2592000, max_size=365),
            CacheType.INTENT: cls(strategy=CacheStrategy.TTL_LRU, ttl=600, max_size=1000),
            CacheType.CONFIG: cls(strategy=CacheStrategy.FIXED_SIZE, ttl=None, max_size=20),
            CacheType.DEVICE_PROMPT: cls(strategy=CacheStrategy.TTL, ttl=None, max_size=1000),
            CacheType.VOICEPRINT_HEALTH: cls(strategy=CacheStrategy.TTL, ttl=600, max_size=100),
            CacheType.AUDIO_DATA: cls(strategy=CacheStrategy.TTL, ttl=600, max_size=100),
        }
        return configs.get(cache_type, cls())
