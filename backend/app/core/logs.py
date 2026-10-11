import json
import logging
import sys
from datetime import UTC, datetime


class FormatoJson(logging.Formatter):
    """Una línea JSON por registro. Los campos extra van en `extra={"campos": {...}}`."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
        linea = {
            "ts": ts.replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            **getattr(record, "campos", {}),
        }
        if record.exc_info:
            linea["exception"] = self.formatException(record.exc_info)
        return json.dumps(linea, ensure_ascii=False, default=str)


def configurar_logs(nivel: str) -> None:
    logger = logging.getLogger("miseventos")
    logger.setLevel(nivel)
    if not any(isinstance(h.formatter, FormatoJson) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(FormatoJson())
        logger.addHandler(handler)
