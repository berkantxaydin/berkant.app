from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, Type, TypeVar
import json

T = TypeVar('T', bound='BaseRowModel')

@dataclass
class BaseRowModel:
    @classmethod
    def from_row(cls: Type[T], row: Any) -> Optional[T]:
        if not row: return None
        data = dict(row)
        # Handle JSON fields if they are strings
        for field_name, field_def in cls.__dataclass_fields__.items():
            if field_def.type in [dict, Dict[str, Any]] and isinstance(data.get(field_name), str):
                try:
                    data[field_name] = json.loads(data[field_name])
                except:
                    data[field_name] = {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class User(BaseRowModel):
    id: Optional[int] = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    is_admin: bool = False
    created_at: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GodotGame(BaseRowModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    jam_id: Optional[int] = None
    title: str = ""
    description: str = ""
    game_url: str = ""
    validation_status: str = "Pending"
    views: int = 0
    icon_url: Optional[str] = None
    github_url: Optional[str] = None
    created_at: Optional[str] = None
    username: Optional[str] = None
    likes: int = 0

@dataclass
class CVCatalog(BaseRowModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    title: str = ""
    location: str = ""
    summary: str = ""
    cv_data: Dict[str, Any] = field(default_factory=dict)
    custom_htmx: str = ""
    photo_url: Optional[str] = None
    github_url: Optional[str] = None
    created_at: Optional[str] = None
    username: Optional[str] = None
    author_is_admin: bool = False

@dataclass
class GameJam(BaseRowModel):
    id: Optional[int] = None
    title: str = ""
    theme: str = ""
    start_time: str = ""
    end_time: str = ""
    youtube_url: str = ""
    image_url: Optional[str] = None

@dataclass
class ChatMessage(BaseRowModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    room_id: int = 1
    content: str = ""
    image_url: Optional[str] = None
    created_at: Optional[str] = None
    username: Optional[str] = None
    is_admin: bool = False

@dataclass
class GameComment(BaseRowModel):
    id: Optional[int] = None
    user_id: Optional[int] = None
    game_id: Optional[int] = None
    content: str = ""
    created_at: Optional[str] = None
    username: Optional[str] = None

@dataclass
class AnalyticsLog(BaseRowModel):
    id: Optional[int] = None
    method: str = ""
    path: str = ""
    visitor_id: str = ""
    is_htmx: bool = False
    status_code: int = 0
    duration_ms: int = 0
    created_at: Optional[str] = None
