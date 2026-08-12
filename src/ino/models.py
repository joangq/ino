from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class PortProperties(BaseModel):
    pid: str | None = None
    vid: str | None = None
    serialNumber: str | None = None
    configuration: str | None = None
    manufacturer: str | None = None
    product: str | None = None


class Port(BaseModel):
    address: str
    label: str
    protocol: str
    protocol_label: str
    properties: PortProperties
    hardware_id: str | None = None


class MatchingBoard(BaseModel):
    name: str
    fqbn: str


class DetectedPort(BaseModel):
    port: Port
    matching_boards: list[MatchingBoard] = Field(default_factory=list)


class BoardList(BaseModel):
    detected_ports: list[DetectedPort]


class Library(BaseModel):
    name: str
    author: str | None = None
    maintainer: str | None = None
    sentence: str | None = None
    paragraph: str | None = None
    website: str | None = None
    category: str | None = None
    architectures: list[str] = Field(default_factory=list)
    install_dir: str | None = None
    source_dir: str | None = None
    version: str | None = None
    license: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    location: str | None = None
    layout: str | None = None
    examples: list[str] = Field(default_factory=list)
    provides_includes: list[str] = Field(default_factory=list)
    compatible_with: dict[str, Any] = Field(default_factory=dict)


class InstalledLibrary(BaseModel):
    library: Library


class LibraryList(BaseModel):
    installed_libraries: list[InstalledLibrary] = Field(default_factory=list)


class Pin(BaseModel):
    pin: int
    tag: str

class BoardSpec(BaseModel):
    name: str
    cpu: str | None = None

class Sketch(BaseModel):
    name: str
    pins: list[Pin] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    board: str | BoardSpec

class InoProject(BaseModel):
    sketch: Sketch