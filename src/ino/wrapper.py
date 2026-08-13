from ino.cmd import CommandRunner
from argbuilder import Command as CommandBase, Field
from pathlib import Path
from shutil import which
from .models import BoardList, LibList
from typing import Any, cast, Never, override
import subprocess
from ino.loggable import Loggable
from ino.common import throw
from ino.loggable import log
import platform

class Command(CommandBase, Loggable):
    @override
    def get_logger(self):
        """Walks the parent chain for a logger set via set_logger."""
        node: object | None = self
        while node is not None:
            logger = getattr(node, "_logger", None)
            if logger is not None:
                return logger
            node = getattr(node, "_parent", None)
        return super().get_logger()

    @override
    def run(self, **kwargs) -> Any:
        """Runs the built command via subprocess.run. Kwargs are passed through."""
        DEFAULT_KWARGS: dict[str, Any] = dict(
            text=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        kwargs = DEFAULT_KWARGS | cast(dict[str, Any], kwargs)
        subprocess_kwargs = {k: v for k, v in kwargs.items() if k not in ('verbose', 'pretty')}
        command_runner = CommandRunner(**subprocess_kwargs)
        command_runner.set_logger(self.logger)
        args = self.build()

        return command_runner.run(*args)

class ArduinoCli(Command):
    def arg0(self) -> str:
        arduino_cli_path = which('arduino-cli')
        
        if arduino_cli_path is not None:
            return arduino_cli_path
        
        linux_options = [
            Path('.').resolve() / 'arduino-cli',
            Path('.').resolve() / 'bin' / 'arduino-cli',
            Path('..').resolve() / 'bin' / 'arduino-cli',
            Path('../..').resolve() / 'bin' / 'arduino-cli',
        ]
        
        windows_options = [
            Path('.').resolve() / 'arduino-cli.exe',
            Path('.').resolve() / 'bin' / 'arduino-cli.exe',
            Path('..').resolve() / 'bin' / 'arduino-cli.exe',
            Path('../..').resolve() / 'bin' / 'arduino-cli.exe',
        ]

        if platform.system() == 'Linux':
            options = linux_options
        elif platform.system() == 'Windows':
            options = windows_options
        else:
            raise ValueError(f'Unsupported system: {platform.system()}')

        for option in options:
            if option.exists():
                return str(option)

        raise FileNotFoundError('arduino-cli not found')

    class lib(Command):
        class list(Command):
            format: str = Field('--format={value}', default='json')

            def run(self, **kwargs) -> Any:
                return super().run(**kwargs).and_then(
                    (lambda x: LibList.model_validate_json(
                        x.stdout.decode('utf-8')
                    ))
                )
    
    class compile(Command):
        fqbn: str = Field('--fqbn={value}')
        path: str = Field('{value}')

        def run(self, **kwargs) -> Any:
            return super().run(**kwargs).and_then(
                log(lambda x: self.logger.info(f"{x.stdout.decode('utf-8').strip()}"))
            )
    
    class upload(Command):
        port: str = Field('--port={value}')
        fqbn: str = Field('--fqbn={value}')
        path: str = Field('{value}')

    class board(Command):
        class list(Command):
            format: str = Field(parts=['--format={value}'], default='json')
            discovery_timeout: str = Field(
                parts=['--discovery-timeout={value}'],
                default='5s',
            )

            def run(self, **kwargs) -> BoardList: # ty: ignore[invalid-method-override]
                return ( super().run()
                        .or_else(
                            lambda x: throw(Exception(x.stderr.decode('utf-8')))
                        )
                        .and_then(lambda x: 
                            BoardList.model_validate_json(
                                x.stdout.decode('utf-8')
                            )
                        )
                )