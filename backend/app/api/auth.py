from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencias import (
    ConfigApp,
    RepoUsuarios,
    UsuarioActual,
    formulario_sin_caracter_nulo,
)
from app.api.errores import respuestas_de_error
from app.core.permisos import permisos_de
from app.schemas.auth import (
    CambioContrasenaEntrada,
    Mensaje,
    PerfilConPermisos,
    RegistroEntrada,
    TokenAcceso,
    UsuarioSalida,
)
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
    dependencies=[Depends(formulario_sin_caracter_nulo)],
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
    description="Los datos del usuario dueño del access token y los permisos de su rol.",
    responses=respuestas_de_error(401),
)
def me(usuario: UsuarioActual) -> PerfilConPermisos:
    datos = UsuarioSalida.model_validate(usuario, from_attributes=True)
    return PerfilConPermisos(**datos.model_dump(), permisos=permisos_de(usuario))


@router.patch(
    "/me/password",
    summary="Cambiar la contraseña",
    description="Pide la contraseña actual. Devuelve un access token nuevo, como el login.",
    responses=respuestas_de_error(401, 422),
)
def cambiar_contrasena(
    datos: CambioContrasenaEntrada, usuario: UsuarioActual, settings: ConfigApp
) -> TokenAcceso:
    token = autenticacion.cambiar_contrasena(
        usuario,
        datos.current_password,
        datos.new_password,
        settings.jwt_secret,
        settings.access_token_minutes,
    )
    return TokenAcceso(access_token=token, expires_in=settings.access_token_minutes * 60)
