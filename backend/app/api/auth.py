from fastapi import APIRouter, status

from app.schemas.auth import Mensaje, RegistroEntrada

router = APIRouter(prefix="/auth", tags=["autenticación"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def registrar(datos: RegistroEntrada) -> Mensaje:
    return Mensaje(message="Registro recibido. Iniciá sesión con tu correo y contraseña.")
