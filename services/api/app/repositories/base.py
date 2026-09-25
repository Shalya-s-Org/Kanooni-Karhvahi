from typing import Generic, TypeVar, Type, Optional, List, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic asynchronous base repository providing standard CRUD operations.
    Follows repository pattern to decouple persistence logic from business services.
    """

    def __init__(self, model_class: Type[ModelT], db: AsyncSession):
        self.model_class = model_class
        self.db = db

    async def get_by_id(self, id: Any) -> Optional[ModelT]:
        result = await self.db.execute(select(self.model_class).where(self.model_class.id == id))
        return result.scalars().first()

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[ModelT]:
        result = await self.db.execute(select(self.model_class).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def create(self, instance: ModelT) -> ModelT:
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete_by_id(self, id: Any) -> bool:
        stmt = delete(self.model_class).where(self.model_class.id == id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
