from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.db import get_session
from app.repositories.salud import base_responde

router = APIRouter(tags=["salud"])


@router.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    base_responde(session)
    return {"status": "ok"}
