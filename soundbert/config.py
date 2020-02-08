import dataclasses
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    database_url: str
    default_prefix: str
    sound_path: str
    log_level: str = 'INFO'

    @classmethod
    def from_env(cls) -> 'Config':
        load_dotenv()

        fields = {}
        for field in dataclasses.fields(cls):
            value = os.getenv('SOUNDBERT_' + field.name.upper())
            if value is not None:
                fields[field.name] = value

        return cls(**fields)
