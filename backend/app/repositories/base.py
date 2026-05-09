from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from ..core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: Session) -> None:
        self.model = model
        self.db = db

    def get(self, pk: object) -> ModelType | None:
        return self.db.get(self.model, pk)

    def add(self, instance: ModelType) -> ModelType:
        self.db.add(instance)
        return instance

    def delete(self, instance: ModelType) -> None:
        self.db.delete(instance)

    def commit(self) -> None:
        self.db.commit()

    def flush(self) -> None:
        self.db.flush()
