from sqlmodel import SQLModel

CONVENCION_DE_NOMBRES: dict[str, str] = {}

SQLModel.metadata.naming_convention = CONVENCION_DE_NOMBRES
