from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencias import RepoUsuarios
from app.api.errores import respuestas_de_error
from app.schemas.auth import Mensaje, RegistroEntrada
from app.services import autenticacion

router = APIRouter(prefix="/auth", tags=["autenticación"])

# Igual exista o no el email: la respuesta no revela qué correos están registrados.
MENSAJE_REGISTRO = "Registro recibido. Iniciá sesión con tu correo y contraseña."


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Registrarse",
    description="Crea un usuario asistente. Responde lo mismo aunque el email ya exista.",
    responses=respuestas_de_error(422),
)
def registrar(datos: RegistroEntrada, repo: RepoUsuarios) -> Mensaje:
    autenticacion.registrar(repo, datos.email, datos.password, datos.full_name)
    return Mensaje(message=MENSAJE_REGISTRO)


@router.post("/login")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], repo: RepoUsuarios
) -> dict[str, str]:
    autenticacion.autenticar(repo, form.username, form.password)
    return {}


@router.get("/me")
def me() -> dict[str, str]:
    return {}
