from dataclasses import dataclass, field
from datetime import datetime
import json

@dataclass
class User:
    id: int = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    is_admin: bool = False
    created_at: str = None
    preferences: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row):
        if not row: return None
        data = dict(row)
        if isinstance(data.get('preferences'), str):
            try:
                data['preferences'] = json.loads(data['preferences'])
            except:
                data['preferences'] = {}
        # Filter keys that doesn't exist in dataclass fields if any
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class GodotGame:
    id: int = None
    user_id: int = None
    jam_id: int = None
    title: str = ""
    description: str = ""
    game_url: str = ""
    validation_status: str = "Pending"
    views: int = 0
    created_at: str = None
    username: str = None # Joined field
    likes: int = 0       # Joined field

    @classmethod
    def from_row(cls, row):
        if not row: return None
        data = dict(row)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class CVCatalog:
    id: int = None
    user_id: int = None
    title: str = ""
    summary: str = ""
    cv_data: dict = field(default_factory=dict)
    custom_htmx: str = ""
    created_at: str = None
    username: str = None # Joined field

    @classmethod
    def from_row(cls, row):
        if not row: return None
        data = dict(row)
        if isinstance(data.get('cv_data'), str):
            try:
                data['cv_data'] = json.loads(data['cv_data'])
            except:
                data['cv_data'] = {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class GameJam:
    id: int = None
    title: str = ""
    theme: str = ""
    start_time: str = ""
    end_time: str = ""
    youtube_url: str = ""

    @classmethod
    def from_row(cls, row):
        if not row: return None
        data = dict(row)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class ChatMessage:
    id: int = None
    user_id: int = None
    room_id: int = 1
    content: str = ""
    created_at: str = None
    username: str = None # Joined field

    @classmethod
    def from_row(cls, row):
        if not row: return None
        data = dict(row)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class AnalyticsLog:
    id: int = None
    method: str = ""
    path: str = ""
    ip_address: str = ""
    visitor_id: str = ""
    is_htmx: bool = False
    status_code: int = 0
    duration_ms: int = 0
    created_at: str = None

    @classmethod
    def from_row(cls, row):
        if not row: return None
        data = dict(row)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
