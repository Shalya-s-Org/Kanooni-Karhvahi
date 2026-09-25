from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
import os
import aiofiles
from app.core.config import settings
from app.core.logging import logger


class DocumentStorageProvider(ABC):
    """
    Abstract Base Class for ephemeral document file storage.
    Enables swapping between local disk, AWS S3, or encrypted memory stores.
    """

    @abstractmethod
    async def save_file(self, file_content: bytes, destination_path: str) -> str:
        """
        Saves file bytes and returns the stored file URI or path.
        """
        pass

    @abstractmethod
    async def read_file(self, path: str) -> bytes:
        """
        Reads file bytes from storage.
        """
        pass

    @abstractmethod
    async def delete_file(self, path: str) -> bool:
        """
        Permanently purges file from storage (privacy compliance).
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Checks if file exists.
        """
        pass


class LocalDocumentStorage(DocumentStorageProvider):
    """
    Local filesystem storage provider for development.
    """

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or settings.STORAGE_LOCAL_DIR
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve(self, path: str) -> str:
        return os.path.join(self.base_dir, os.path.basename(path))

    async def save_file(self, file_content: bytes, destination_path: str) -> str:
        target = self._resolve(destination_path)
        async with aiofiles.open(target, "wb") as f:
            await f.write(file_content)
        return target

    async def read_file(self, path: str) -> bytes:
        target = self._resolve(path)
        async with aiofiles.open(target, "rb") as f:
            return await f.read()

    async def delete_file(self, path: str) -> bool:
        target = self._resolve(path)
        try:
            if os.path.exists(target):
                os.remove(target)
                return True
            return False
        except Exception as e:
            logger.error("Failed to delete file %s: %s", target, e)
            return False

    async def exists(self, path: str) -> bool:
        return os.path.exists(self._resolve(path))
