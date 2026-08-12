from abc import ABC, abstractmethod
from ino.common import ComPort
from ino.wrapper import ArduinoCli
from pathlib import Path
from typing import Self
from ino.common import throw
from ino.models import BoardSpec
from ino.models import DetectedPort

BOARD_REGISTRY = {}

class Board(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def cpu(self) -> str | None: ...

    port: ComPort | None = None

    @property
    def fqbn(self) -> str:
        parts = [
            self.name,
            f'cpu={self.cpu}' if self.cpu else None,
        ]

        return ':'.join(x for x in parts if x)
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BOARD_REGISTRY[cls.name] = cls

    def __init__(self, cli: ArduinoCli | None = None):
        self.cli = cli or ArduinoCli()

    def compile(self, dir: Path|str):
        return self.cli.compile(
            fqbn=self.fqbn, 
            path=str(Path(dir).resolve())
        ).run().or_else(
            lambda x: throw(Exception(x.stderr.decode('utf-8')))
        ).and_then(
            lambda x: x.stdout.decode('utf-8').strip()
        )
    
    def connect(self, port: str|ComPort) -> Self:
        self.port = ComPort(port)
        return self

    def upload(self, path: Path|str):
        if self.port is None:
            raise ValueError('Port not set')

        return self.cli.upload(
            fqbn=self.fqbn,
            port=str(self.port),
            path=str(Path(path).resolve())
        ).run().or_else(
            lambda x: throw(Exception(x.stderr.decode('latin1').strip()))
        ).and_then(
            lambda x: x.stdout.decode('utf-8').strip()
        )

def make_board(spec: str | BoardSpec, registry: dict | None = None) -> type[Board]:
    registry = registry or BOARD_REGISTRY
    if isinstance(spec, str):
        return registry[spec]

    class _(Board):
        name = spec.name
        cpu = spec.cpu

    return _

class BoardFactory:
    def __init__(self, cli: ArduinoCli | None = None):
        self.cli = cli or ArduinoCli()

    def match_port[T: Board](self, detected_port: DetectedPort, board_type: type[T]) -> T | None:
        if not detected_port.matching_boards:
            return None

        for matching_board in detected_port.matching_boards:
            if matching_board.fqbn == board_type.name:
                return board_type(cli=self.cli).connect(detected_port.port.address)
        
        return None


    def resolve[T: Board](self, board_type: type[T]) -> T:
        board_list = self.cli.board().list().run()
        
        for detected_port in board_list.detected_ports:
            board = self.match_port(detected_port, board_type)

            if board is not None:
                return board

        raise ValueError(f'Board {board_type.name} not found')
