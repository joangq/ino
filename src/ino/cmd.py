from pathlib import Path
import subprocess
from typing import Callable, Self
from .loggable import Loggable

class CompletedProcess(subprocess.CompletedProcess):
    """
    Mónada Resultado aplicada a subprocess.CompletedProcess.
    Inspirado en el el tipo Result de Rust.

    https://doc.rust-lang.org/std/result/
    """
    @classmethod
    def from_other(cls, other: subprocess.CompletedProcess) -> Self:
        # HACK: This only wors when two objects have compatible memory layouts (__slots__)
        self = cls.__new__(cls)
        self.__dict__.update(other.__dict__)
        self.__class__ = cls
        return self

    def is_ok(self) -> bool:
        return self.returncode == 0

    def and_then[T](self, processor: Callable[[Self], T]) -> T|Self:
        # Calls 'processor' with self if is Ok, otherwise returns self
        if self.is_ok():
            return processor(self)
        
        return self

    def or_else[T](self, processor: Callable[[Self], T]) -> T|Self:
        # Calls 'processor' with self if is Error, otherwise returns self
        if not self.is_ok():
            return processor(self)
        
        return self

class CommandRunner(Loggable):
    def __init__(
        self,
        bufsize=-1,
        executable=None,
        stdin=None,
        stdout=None,
        stderr=None,
        preexec_fn=None,
        close_fds=True,
        shell=False,
        cwd=None,
        env=None,
        universal_newlines=None,
        startupinfo=None,
        creationflags=0,
        restore_signals=True,
        start_new_session=False,
        pass_fds=(),
        input=None, 
        capture_output=False, 
        timeout=None, 
        check=False,
        *,
        user=None,
        group=None,
        extra_groups=None,
        encoding=None,
        errors=None,
        text=None,
        umask=-1,
        pipesize=-1,
        process_group=None,
        **kwargs,
    ):
        _locals = locals()
        _locals.pop('self')
        kwargs = _locals.pop('kwargs')
        _locals.update(kwargs)

        self.default_params = _locals

    def run(
        self, 
        *args: str, 
        msg: None | str = None,
    ) -> CompletedProcess:
        logger = self.logger

        if msg:
            logger.info(f"{msg}")

        [path, *extra_args] = args
        path = Path(path).resolve().name
        command = ' '.join([path, *extra_args])

        # Notacion inspirada en los tipos Sesion
        # https://en.wikipedia.org/wiki/Session_type
        # "!" significa 'enviar' datos a un canal,
        # "?" significa 'recibir' datos de un canal.
        # En este caso, el canal está implicito, por lo que
        # sólo mostramos lo que se envia (el comando) y lo
        # que se recibe (resultado de la ejecución).

        logger.debug(f"[bold cyan][!][/bold cyan] {command}")

        result = subprocess.run(args, **self.default_params)

        PREFIX = "[bold][green][?][/bold][/green]" if result.returncode == 0 else "[bold][red][!][/bold][/red]"

        logger.debug(f"{PREFIX} {result.returncode} [dim]<<< {command}[/dim]")

        return CompletedProcess.from_other(result)