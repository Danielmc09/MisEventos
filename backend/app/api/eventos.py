from fastapi import APIRouter

router = APIRouter(prefix="/events", tags=["eventos"])


@router.post("")
def crear() -> None:
    raise NotImplementedError
