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

    # Create
    async def store(self, guild_id: int, name: str, file: Path, overwrite=False):
        try:
            await self._move(guild_id, name, file, overwrite)
        finally:
            file.unlink(missing_ok=True)


    @abc.abstractmethod
    async def _move(self, guild_id: int, name: str, file: Path, overwrite=False):
        """
        Move sound to its final location.
        """
        raise NotImplementedError

    # Read
    @abc.abstractmethod
    async def retrieve(self, guild_id: int, name: str) -> Union[Path, str]:
        raise NotImplementedError

    # Update
    @abc.abstractmethod
    async def rename(self, guild_id: int, old_name: str, new_name: str):
        raise NotImplementedError

    # Delete
    @abc.abstractmethod
    async def delete(self, guild_id: int, name: str):
        raise NotImplementedError



class LocalSoundStorage(SoundStorage):
    name = 'local'
    config_options = ('directory',)

    def __init__(self, directory):
        super().__init__(directory)
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=True)


    async def _move(self, guild_id: int, name: str, file: Path, overwrite=False):
        server_dir = self.directory / str(guild_id)
        server_dir.mkdir(exist_ok=True)
        destination = server_dir / name
        if destination.exists() and not overwrite:
            raise FileExistsError

        shutil.move(str(file), str(destination))

    async def retrieve(self, guild_id: int, name: str):
        file = self.directory / str(guild_id) / name
        if not file.is_file():
            raise FileNotFoundError
        return file

    async def rename(self, guild_id: int, old_name: str, new_name: str):
        file = self.directory / str(guild_id) / old_name
        # todo: will this work in docker volumes? or will we have to use shutil?
        file.rename(new_name)

    async def delete(self, guild_id: int, name: str):
        file = self.directory / str(guild_id) / name
        file.unlink()