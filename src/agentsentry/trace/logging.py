"""Redact rendered library log messages and tracebacks, including SDK validation errors."""

import logging
from agentsentry.context.scanner import redact


class RedactingFormatter(logging.Formatter):
    def __init__(self, original):
        super().__init__()
        self.original = original or logging.Formatter()

    def format(self, record):
        return redact(self.original.format(record))


def install_redaction():
    loggers = [logging.getLogger()] + [
        v
        for v in logging.Logger.manager.loggerDict.values()
        if isinstance(v, logging.Logger)
    ]
    for logger in loggers:
        for handler in logger.handlers:
            if not isinstance(handler.formatter, RedactingFormatter):
                handler.setFormatter(RedactingFormatter(handler.formatter))
