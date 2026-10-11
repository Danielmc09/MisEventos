from pydantic import BaseModel


class RegistroEntrada(BaseModel):
    email: str
    password: str
    full_name: str | None = None


class Mensaje(BaseModel):
    message: str
