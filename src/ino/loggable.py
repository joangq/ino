from __future__ import annotations

import logging
from types import TracebackType
from typing import Mapping, Protocol, Self, TypeAlias, runtime_checkable

Level: TypeAlias = int | str

ExcInfo: TypeAlias = (
    None
    | bool
    | BaseException
    | tuple[type[BaseException], BaseException, TracebackType | None]
    | tuple[None, None, None]
)

Extra: TypeAlias = Mapping[str, object] | None

@runtime_checkable
class LoggerLike(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def level(self) -> int: ...

    @property
    def disabled(self) -> bool: ...

    @property
    def propagate(self) -> bool: ...

    def setLevel(self, level: Level, /) -> None: ...

    def debug(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfo = None,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def info(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfo = None,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def warning(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfo = None,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def warn(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfo = None,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def error(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfo = None,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def exception(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfo = True,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def critical(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfo = None,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def fatal(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfo = None,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def log(
        self,
        level: int,
        msg: object,
        *args: object,
        exc_info: ExcInfo = None,
        extra: Extra = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> None: ...

    def isEnabledFor(self, level: int, /) -> bool: ...

    def getEffectiveLevel(self) -> int: ...

    def hasHandlers(self) -> bool: ...

    def addHandler(self, hdlr: logging.Handler, /) -> None: ...

    def removeHandler(self, hdlr: logging.Handler, /) -> None: ...

    def handle(self, record: logging.LogRecord, /) -> None: ...

    def callHandlers(self, record: logging.LogRecord, /) -> None: ...

    def findCaller(
        self,
        stack_info: bool = False,
        stacklevel: int = 1,
    ) -> tuple[str, int, str, str | None]: ...

    def makeRecord(
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: object,
        args: tuple[object, ...],
        exc_info: ExcInfo,
        func: str | None = None,
        extra: Extra = None,
        sinfo: str | None = None,
    ) -> logging.LogRecord: ...

    def getChild(self, suffix: str, /) -> LoggerLike: ...

class NullLogger(LoggerLike):
    name = '<null_logger>'
    level = logging.NOTSET
    disabled = True
    propagate = False

    def __getattr__(self, name: str):
        return lambda *args, **kwargs: None

NULL_LOGGER = NullLogger()

class Loggable:
    def set_logger(self, logger: logging.Logger | LoggerLike) -> Self:
        self._logger = logger
        return self

    def get_logger(self) -> LoggerLike:
        logger = getattr(self, "_logger", NULL_LOGGER)
        return logger

    @property
    def logger(self) -> LoggerLike:
        return self.get_logger()

def log(f):
    def _(x: Loggable):
        f(x)
        return x
    return _