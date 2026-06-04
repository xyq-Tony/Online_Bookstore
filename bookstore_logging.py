import logging
import os
import socket
import sys
from logging.handlers import SysLogHandler

from flask import g, has_request_context, request
from flask_login import current_user


APP_NAME = "online_bookstore"

DEFAULTS = {
    "BOOKSTORE_LOG_LEVEL": "INFO",
    "BOOKSTORE_LOG_MODE": "both",
    "BOOKSTORE_SYSLOG_HOST": "127.0.0.1",
    "BOOKSTORE_SYSLOG_PORT": "5514",
    "BOOKSTORE_SYSLOG_PROTO": "udp",
    "BOOKSTORE_SYSLOG_FACILITY": "local0",
}

STANDARD_CONTEXT_KEYS = {
    "request_id",
    "method",
    "path",
    "status",
    "duration_ms",
    "client_ip",
    "user",
    "event",
}

RESERVED_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}

SYSLOG_FACILITIES = {
    "auth": SysLogHandler.LOG_AUTH,
    "authpriv": SysLogHandler.LOG_AUTHPRIV,
    "cron": SysLogHandler.LOG_CRON,
    "daemon": SysLogHandler.LOG_DAEMON,
    "kern": SysLogHandler.LOG_KERN,
    "local0": SysLogHandler.LOG_LOCAL0,
    "local1": SysLogHandler.LOG_LOCAL1,
    "local2": SysLogHandler.LOG_LOCAL2,
    "local3": SysLogHandler.LOG_LOCAL3,
    "local4": SysLogHandler.LOG_LOCAL4,
    "local5": SysLogHandler.LOG_LOCAL5,
    "local6": SysLogHandler.LOG_LOCAL6,
    "local7": SysLogHandler.LOG_LOCAL7,
    "lpr": SysLogHandler.LOG_LPR,
    "mail": SysLogHandler.LOG_MAIL,
    "news": SysLogHandler.LOG_NEWS,
    "syslog": SysLogHandler.LOG_SYSLOG,
    "user": SysLogHandler.LOG_USER,
    "uucp": SysLogHandler.LOG_UUCP,
}


def _quote(value):
    if value is None:
        return "-"

    text = str(value)
    safe_text = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    if not safe_text:
        return '""'
    if any(char.isspace() for char in safe_text) or "=" in safe_text:
        return f'"{safe_text}"'
    return safe_text


def _get_client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "-"
    return request.remote_addr or "-"


def _get_current_user():
    try:
        if current_user.is_authenticated:
            return current_user.username
    except Exception:
        return "-"
    return "-"


def _resolve_level():
    level_name = os.getenv("BOOKSTORE_LOG_LEVEL", DEFAULTS["BOOKSTORE_LOG_LEVEL"]).upper()
    return getattr(logging, level_name, logging.INFO)


def _resolve_mode():
    mode = os.getenv("BOOKSTORE_LOG_MODE", DEFAULTS["BOOKSTORE_LOG_MODE"]).lower()
    return mode if mode in {"console", "syslog", "both"} else DEFAULTS["BOOKSTORE_LOG_MODE"]


def _resolve_port():
    raw_port = os.getenv("BOOKSTORE_SYSLOG_PORT", DEFAULTS["BOOKSTORE_SYSLOG_PORT"])
    try:
        return int(raw_port)
    except (TypeError, ValueError):
        return int(DEFAULTS["BOOKSTORE_SYSLOG_PORT"])


def _resolve_proto():
    proto = os.getenv("BOOKSTORE_SYSLOG_PROTO", DEFAULTS["BOOKSTORE_SYSLOG_PROTO"]).lower()
    return proto if proto in {"udp", "tcp"} else DEFAULTS["BOOKSTORE_SYSLOG_PROTO"]


def _resolve_facility():
    facility_name = os.getenv("BOOKSTORE_SYSLOG_FACILITY", DEFAULTS["BOOKSTORE_SYSLOG_FACILITY"]).lower()
    return SYSLOG_FACILITIES.get(facility_name, SysLogHandler.LOG_LOCAL0)


def _config_signature():
    return (
        _resolve_level(),
        _resolve_mode(),
        os.getenv("BOOKSTORE_SYSLOG_HOST", DEFAULTS["BOOKSTORE_SYSLOG_HOST"]),
        _resolve_port(),
        _resolve_proto(),
        _resolve_facility(),
    )


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        defaults = {
            "request_id": "-",
            "method": "-",
            "path": "-",
            "status": "-",
            "duration_ms": "-",
            "client_ip": "-",
            "user": "-",
            "event": "-",
        }

        for key, value in defaults.items():
            if not hasattr(record, key):
                setattr(record, key, value)

        if not has_request_context():
            return True

        if getattr(record, "request_id", "-") == "-":
            record.request_id = getattr(g, "request_id", "-")
        if getattr(record, "method", "-") == "-":
            record.method = request.method
        if getattr(record, "path", "-") == "-":
            record.path = request.path
        if getattr(record, "status", "-") == "-":
            record.status = getattr(g, "response_status", "-")
        if getattr(record, "duration_ms", "-") == "-":
            record.duration_ms = getattr(g, "request_duration_ms", "-")
        if getattr(record, "client_ip", "-") == "-":
            record.client_ip = _get_client_ip()
        if getattr(record, "user", "-") == "-":
            record.user = getattr(g, "log_user", None) or _get_current_user()

        return True


class StructuredFormatter(logging.Formatter):
    def __init__(self, include_timestamp):
        super().__init__(datefmt="%Y-%m-%dT%H:%M:%S")
        self.include_timestamp = include_timestamp

    def format(self, record):
        record.message = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)

        fields = []
        if self.include_timestamp:
            fields.append(("ts", self.formatTime(record, self.datefmt)))

        fields.extend(
            [
                ("level", record.levelname),
                ("app", APP_NAME),
                ("logger", record.name),
                ("event", getattr(record, "event", "-")),
                ("request_id", getattr(record, "request_id", "-")),
                ("method", getattr(record, "method", "-")),
                ("path", getattr(record, "path", "-")),
                ("status", getattr(record, "status", "-")),
                ("duration_ms", getattr(record, "duration_ms", "-")),
                ("user", getattr(record, "user", "-")),
                ("client_ip", getattr(record, "client_ip", "-")),
                ("message", record.message),
            ]
        )

        extra_keys = []
        for key, value in record.__dict__.items():
            if key in RESERVED_LOG_RECORD_KEYS or key in STANDARD_CONTEXT_KEYS:
                continue
            if key.startswith("_"):
                continue
            extra_keys.append((key, value))

        for key, value in sorted(extra_keys):
            fields.append((key, value))

        output = " ".join(f"{key}={_quote(value)}" for key, value in fields)
        if record.exc_text:
            output = f"{output} traceback={_quote(record.exc_text)}"
        return output


class SafeSysLogHandler(SysLogHandler):
    def handleError(self, record):
        if logging.raiseExceptions:
            super().handleError(record)


def _build_console_handler():
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(StructuredFormatter(include_timestamp=True))
    handler.addFilter(RequestContextFilter())
    return handler


def _build_syslog_handler():
    host = os.getenv("BOOKSTORE_SYSLOG_HOST", DEFAULTS["BOOKSTORE_SYSLOG_HOST"])
    port = _resolve_port()
    proto = _resolve_proto()
    socktype = socket.SOCK_STREAM if proto == "tcp" else socket.SOCK_DGRAM

    handler = SafeSysLogHandler(
        address=(host, port),
        facility=_resolve_facility(),
        socktype=socktype,
    )
    handler.ident = "online-bookstore "
    handler.append_nul = False
    handler.setFormatter(StructuredFormatter(include_timestamp=False))
    handler.addFilter(RequestContextFilter())
    return handler


def configure_logging():
    logger = logging.getLogger(APP_NAME)
    signature = _config_signature()

    if getattr(logger, "_bookstore_config_signature", None) == signature:
        return logger

    logger.handlers.clear()
    logger.setLevel(signature[0])
    logger.propagate = False

    mode = signature[1]
    if mode in {"console", "both"}:
        logger.addHandler(_build_console_handler())
    if mode in {"syslog", "both"}:
        logger.addHandler(_build_syslog_handler())
    if not logger.handlers:
        logger.addHandler(_build_console_handler())

    logger._bookstore_config_signature = signature
    return logger
