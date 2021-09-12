import abc
import inspect
import shutil
from pathlib import Path
from typing import Union, Dict, Type

from . import settings


def get_storage() -> 'SoundStorage':
    providers = SoundStorage.providers()
    try:
        provider = providers[settings.STORAGE_PROVIDER]
    except KeyError as e:
        raise KeyError(
                f'Storage provider "{settings.STORAGE_PROVIDER}" not supported. '
                f'Available providers: {", ".join(providers.keys())}'
        ) from e

    try:
        config = [settings.STORAGE_CONFIG[option] for option in provider.config_options]
    except KeyError as e:
        raise KeyError(
                f'Expected storage config option "STORAGE_{e.args[0].upper()}" to be set.'
        ) from e
    return provider(*config)


class SoundStorage(abc.ABC):
    name = NotImplemented
    config_options = ()

    def __init__(self, *config):
        self.config = dict(zip(self.config_options, config))

    @abc.abstractmethod
    async def retrieve_sound(self, guild_id: int, name: str) -> Union[Path, str]:
        raise NotImplementedError

    async def store_sound(self, guild_id: int, name: str, file: Path, overwrite=False):
        try:
            await self._move_sound(guild_id, name, file, overwrite)
        finally:
            file.unlink(missing_ok=True)

    @abc.abstractmethod
    async def _move_sound(self, guild_id: int, name: str, file: Path, overwrite=False):
        raise NotImplementedError

    @staticmethod
    def providers() -> Dict[str, Type['SoundStorage']]:
        def recursive_subclasses(cls):
            return set(cls.__subclasses__()) | {
                subclass for class_ in cls.__subclasses__() for subclass in recursive_subclasses(class_)
            }

        providers = filter(
                lambda x: not inspect.isabstract(x) and isinstance(x.name, str),
                recursive_subclasses(SoundStorage)
        )
        return {provider.name: provider for provider in providers}


class LocalSoundStorage(SoundStorage):
    name = 'local'
    config_options = ('directory',)

    def __init__(self, directory):
        super().__init__(directory)
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=True)

    async def retrieve_sound(self, guild_id: int, name: str):
        file = self.directory / str(guild_id) / name
        if not file.is_file():
            raise FileNotFoundError
        return file

    async def _move_sound(self, guild_id: int, name: str, file: Path, overwrite=False):
        server_dir = self.directory / str(guild_id)
        server_dir.mkdir(exist_ok=True)
        destination = server_dir / name
        if destination.exists() and not overwrite:
            raise FileExistsError

        shutil.move(str(file), str(destination))
