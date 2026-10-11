from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencias import ConfigApp, RepoUsuarios, UsuarioActual
from app.api.errores import respuestas_de_error
from app.schemas.auth import Mensaje, RegistroEntrada, TokenAcceso, UsuarioSalida
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


@router.post(
    "/login",
    summary="Iniciar sesión",
    description="Formulario OAuth2: `username` es el email. Devuelve un access token (Bearer).",
    responses=respuestas_de_error(401, 422),
)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    repo: RepoUsuarios,
    settings: ConfigApp,
) -> TokenAcceso:
    token = autenticacion.iniciar_sesion(
        repo, form.username, form.password, settings.jwt_secret, settings.access_token_minutes
    )
    return TokenAcceso(access_token=token, expires_in=settings.access_token_minutes * 60)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión",
    description="Sin estado en el servidor: el cliente descarta su access token. Responde 204 "
    "siempre, con token o sin él.",
)
def logout() -> None:
    return None


@router.get(
    "/me",
    summary="Usuario actual",
    description="Los datos del usuario dueño del access token.",
    responses=respuestas_de_error(401),
)
def me(usuario: UsuarioActual) -> UsuarioSalida:
    return UsuarioSalida.model_validate(usuario, from_attributes=True)


@router.patch("/me/password")
def cambiar_contrasena() -> Response:
    return Response(status_code=status.HTTP_501_NOT_IMPLEMENTED)
