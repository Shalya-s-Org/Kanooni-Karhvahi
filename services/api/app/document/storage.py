from abc import ABC, abstractmethod
from typing import Optional
import os
import shutil
import aiofiles
from uuid import UUID
from app.core.config import settings
from app.core.logging import logger


class DocumentStorageProvider(ABC):
    """
    Abstract Base Class for ephemeral document file storage.
    Enables swapping between local disk, encrypted vaults, and cloud object stores.
    """

    @abstractmethod
    async def save_file(self, file_content: bytes, destination_path: str) -> str:
        """
        Saves file bytes and returns the stored relative storage key.
        """
        pass

    @abstractmethod
    async def read_file(self, storage_key: str) -> bytes:
        """
        Reads file bytes from storage.
        """
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """
        Permanently purges file from storage.
        """
        pass

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        """
        Checks if file exists.
        """
        pass

    @abstractmethod
    def delete_document_tree(self, document_id: UUID) -> bool:
        """
        Permanently removes entire document folder tree (original, pages, derived).
        """
        pass


class LocalDocumentStorage(DocumentStorageProvider):
    """
    Local filesystem storage provider with path traversal protection and structured hierarchy.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or settings.STORAGE_LOCAL_DIR)
        os.makedirs(self.base_dir, exist_ok=True)

    def _safe_resolve(self, relative_path: str) -> str:
        """
        Resolves path and guarantees it resides strictly inside self.base_dir to prevent path traversal.
        """
        # Normalize and strip leading slashes/backslashes
        cleaned = relative_path.lstrip("/\\")
        resolved = os.path.abspath(os.path.join(self.base_dir, cleaned))

        if not resolved.startswith(self.base_dir):
            raise ValueError(f"Path traversal detected: {relative_path}")

        return resolved

    def get_document_dir(self, document_id: UUID) -> str:
        doc_dir = os.path.join(self.base_dir, "documents", str(document_id))
        os.makedirs(os.path.join(doc_dir, "original"), exist_ok=True)
        os.makedirs(os.path.join(doc_dir, "pages"), exist_ok=True)
        os.makedirs(os.path.join(doc_dir, "derived"), exist_ok=True)
        return doc_dir

    def generate_storage_key(self, document_id: UUID, category: str, filename: str) -> str:
        # Sanitize filename
        safe_name = os.path.basename(filename).replace("..", "").replace("/", "_").replace("\\", "_")
        return os.path.join("documents", str(document_id), category, safe_name).replace("\\", "/")

    def get_absolute_path(self, storage_key: str) -> str:
        return self._safe_resolve(storage_key)

    async def save_file(self, file_content: bytes, destination_path: str) -> str:
        target = self._safe_resolve(destination_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        async with aiofiles.open(target, "wb") as f:
            await f.write(file_content)
        return destination_path.replace("\\", "/")

    def save_file_sync(self, file_content: bytes, destination_path: str) -> str:
        target = self._safe_resolve(destination_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(file_content)
        return destination_path.replace("\\", "/")

    async def read_file(self, storage_key: str) -> bytes:
        target = self._safe_resolve(storage_key)
        async with aiofiles.open(target, "rb") as f:
            return await f.read()

    def read_file_sync(self, storage_key: str) -> bytes:
        target = self._safe_resolve(storage_key)
        with open(target, "rb") as f:
            return f.read()

    async def delete_file(self, storage_key: str) -> bool:
        target = self._safe_resolve(storage_key)
        try:
            if os.path.exists(target):
                os.remove(target)
                return True
            return False
        except Exception as e:
            logger.error("Failed to delete file %s: %s", target, e)
            return False

    async def exists(self, storage_key: str) -> bool:
        return os.path.exists(self._safe_resolve(storage_key))

    def exists_sync(self, storage_key: str) -> bool:
        return os.path.exists(self._safe_resolve(storage_key))

    def delete_document_tree(self, document_id: UUID) -> bool:
        doc_dir = os.path.join(self.base_dir, "documents", str(document_id))
        try:
            if os.path.exists(doc_dir):
                shutil.rmtree(doc_dir)
                return True
            return False
        except Exception as e:
            logger.error("Failed to delete document tree for %s: %s", document_id, e)
            return False


# Default storage singleton
document_storage = LocalDocumentStorage()
