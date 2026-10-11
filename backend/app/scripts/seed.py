import argparse
from collections.abc import Sequence
from dataclasses import dataclass

from sqlmodel import Session

from app.core.config import Settings


@dataclass(frozen=True)
class CredencialesDemo:
    admin_email: str
    admin_password: str
    demo_password: str


def credenciales_demo(settings: Settings) -> CredencialesDemo:
    return CredencialesDemo(
        admin_email=settings.admin_email or "",
        admin_password=settings.admin_password or "",
        demo_password=settings.demo_password or "",
    )


def sembrar(session: Session, credenciales: CredencialesDemo) -> None:
    pass


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo-si-seed-demo", action="store_true")
    parser.parse_args(argv)


if __name__ == "__main__":
    main()
