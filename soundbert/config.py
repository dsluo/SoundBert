import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    database_url: str
    default_prefix: str
    sound_path: Path

    @classmethod
    def from_env(cls) -> 'Config':
        load_dotenv()

        token = os.getenv('SOUNDBERT_TOKEN')
        database_url = os.getenv('SOUNDBERT_DATABASE_URL')
        default_prefix = os.getenv('SOUNDBERT_DEFAULT_PREFIX')
        sound_path = os.getenv('SOUNDBERT_SOUND_PATH')

        return cls(token, database_url, default_prefix, sound_path)