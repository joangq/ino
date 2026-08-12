from ino.loggable import Loggable, LoggerLike
import logging
import tomllib
from pathlib import Path

import click
import tomli_w
from rich.console import Console
from rich.logging import RichHandler

from ino.board import BoardFactory, make_board
from ino.models import InoProject
from ino.wrapper import ArduinoCli


console = Console()

rich_handler = RichHandler(
    rich_tracebacks=True,
    markup=True,
    show_path=False,
    show_time=True,
    omit_repeated_times=False,
    show_level=True,
    console=console,
)

logging.basicConfig(
    level=logging.DEBUG,
    format=r"[purple]\[%(name)10s][/purple] %(message)s",
    datefmt="[%X]",
    handlers=[rich_handler],
)


def normalize_loglevel(loglevel: str) -> str:
    return loglevel.upper()


class CommandState(Loggable):
    """Holds project state for a CLI command. Takes the root logger and scopes children itself."""

    def __init__(
        self,
        path: Path,
        logger: LoggerLike | logging.Logger,
        command: str,
        loglevel: str = "INFO",
        cli: ArduinoCli | None = None,
    ) -> None:
        self.cli = cli or ArduinoCli()
        self.set_logger(self._get_child_logger(logger, command, loglevel))

        self.path = path
        self.config_path = path / "ino.toml"

        self.config = self._load_config()
        self.arduino = self._create_arduino(self.cli)

    @staticmethod
    def _get_child_logger(
        root: LoggerLike | logging.Logger,
        command: str,
        loglevel: str = "INFO",
    ) -> LoggerLike | logging.Logger:
        """Derive a command-scoped logger from the root and apply the log level."""
        logger = root.getChild(command)
        logger.setLevel(normalize_loglevel(loglevel))
        return logger

    def _load_config(self) -> InoProject:
        if not self.config_path.exists():
            raise click.ClickException(
                f"No ino.toml found in {self.path}"
            )

        try:
            data = tomllib.loads(self.config_path.read_text())
            return InoProject.model_validate(data)
        except Exception as exc:
            raise click.ClickException(
                f"Failed to load {self.config_path}: {exc}"
            ) from exc

    def _create_arduino(self, cli: ArduinoCli):
        board = make_board(self.config.sketch.board)

        cli.set_logger(self.logger.getChild("ArduinoCli"))

        return BoardFactory(cli).resolve(board)

    def check_libs(self) -> None:
        lib_list = self.cli.lib().list().run()
        
        for lib in self.config.sketch.dependencies:
            if not any(lib == installed_lib.library.name for installed_lib in lib_list.installed_libraries):
                raise click.ClickException(f"Library '{lib}' not found")


    def compile(self) -> None:
        self.check_libs()

        self.logger.info(f"Compiling project '{self.config.sketch.name}'")
        self.logger.info(f"Target: board '{self.arduino.fqbn}'")
        self.arduino.compile(self.path)

    def upload(self) -> None:
        self.check_libs()

        self.logger.info(f"Uploading project '{self.config.sketch.name}'")
        self.logger.info(f"Target: board '{self.arduino.fqbn}' at port '{self.arduino.port}'")
        self.arduino.upload(self.path)
        self.logger.info(f"[green]Project uploaded successfully.[/green]")

    def deploy(self) -> None:
        self.compile()
        self.upload()



PROJECT_PATH_OPTION = click.option(
    "-p", "--path",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        path_type=Path,
    ),
    default=".",
    show_default=True,
    help="Project directory.",
)

LOGLEVEL_OPTION = click.option(
    "--loglevel",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    default="INFO",
    help="Set the log level.",
)

def common_arguments(f):
    return LOGLEVEL_OPTION(PROJECT_PATH_OPTION(f))

@click.group()
@click.pass_context
def main(ctx: click.Context) -> None:
    ctx.obj = {
        "logger": logging.getLogger("ino")
    }


@main.command()
@common_arguments
@click.pass_context
def compile(ctx: click.Context, path: Path, loglevel: str) -> None:
    """Compile an ino project."""
    CommandState(path, ctx.obj["logger"], "compile", loglevel).compile()


@main.command()
@common_arguments
@click.pass_context
def upload(ctx: click.Context, path: Path, loglevel: str) -> None:
    """Upload an ino project."""
    CommandState(path, ctx.obj["logger"], "upload", loglevel).upload()


@main.command()
@common_arguments
@click.pass_context
def deploy(ctx: click.Context, path: Path, loglevel: str) -> None:
    """Compile and upload an ino project."""
    CommandState(path, ctx.obj["logger"], "deploy", loglevel).deploy()

@main.command()
@common_arguments
@click.pass_context
def init(ctx: click.Context, path: Path, loglevel: str) -> None:
    """Initialize a new ino project."""
    logger = CommandState._get_child_logger(ctx.obj["logger"], "init", loglevel)

    path.mkdir(parents=True, exist_ok=True)
    toml_path = path / "ino.toml"

    if toml_path.exists():
        raise click.ClickException(f"Project already initialized in {path}")

    toml_path.write_text(f"""\
[sketch]
name = '{path.stem}'
pins = []

dependencies = []

board = {{ name = "arduino:avr:uno" }}
"""
    )

    logger.info(f"[green]Project initialized successfully.[/green]")


@main.command("add")
@common_arguments
@click.argument("dependencies", nargs=-1, required=True)
@click.pass_context
def add(
    ctx: click.Context,
    path: Path,
    dependencies: tuple[str, ...],
    loglevel: str,
) -> None:
    """Add dependencies to an ino project."""
    logger = CommandState._get_child_logger(ctx.obj["logger"], "add", loglevel)

    config_path = path / "ino.toml"
    if not config_path.exists():
        raise click.ClickException(f"No ino.toml found in {path}")

    try:
        data = tomllib.loads(config_path.read_text())
        config = InoProject.model_validate(data)
    except Exception as exc:
        raise click.ClickException(f"Failed to load {config_path}: {exc}") from exc

    existing = set(config.sketch.dependencies)
    added: list[str] = []
    for dependency in dependencies:
        if dependency in existing:
            logger.info(f"Dependency '{dependency}' already present, skipping")
            continue
        config.sketch.dependencies.append(dependency)
        existing.add(dependency)
        added.append(dependency)

    config_path.write_text(
        tomli_w.dumps(config.model_dump(mode="python", exclude_none=True))
    )

    if added:
        logger.info(f"[green]Added dependencies: {', '.join(added)}[/green]")
    else:
        logger.info("No new dependencies to add")


if __name__ == "__main__":
    main()