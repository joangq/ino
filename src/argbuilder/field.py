from typing import Any, Callable, Final, Iterable, Literal, cast
from dataclasses import dataclass, asdict
from warnings import deprecated

VALUE_TOKEN = "{value}"

class NotSet(object):
    def __repr__(self) -> str:
        return f'NOT_SET({hex(id(self))})'

NOT_SET = NotSet()

type Maybe[T] = T|NotSet
# type TypeAnnotation[T] = Maybe[T]
# type Default[T] = Maybe[T]

DATACLASS_OPTIONS = dict(
    init         = True,
    repr         = True,
    eq           = True,
    order        = False,
    unsafe_hash  = False,
    frozen       = False,
    match_args   = False,
    kw_only      = False,
    slots        = False,
    weakref_slot = False,
)

@dataclass(**DATACLASS_OPTIONS)
class Field[T: Any]:
    type TypeAnnotation = Maybe[type[T]]
    type Default = Maybe[T]
    type SerializerType = Callable[[T], Iterable[str]]

    parts: Iterable[str]
    cls: None | type[T]
    serializer: SerializerType
    default: Default = NOT_SET
    annotation: TypeAnnotation = NOT_SET

    @property
    @deprecated("Field 'string' is deprecated, use 'parts' instead.")
    def string(self) -> Iterable[str]:
        return self.parts

    def dump(
        self, 
        mode: Literal['json', 'python'] = 'python', 
    ) -> dict:
        base = asdict(self)
        base.pop('cls')

        if mode == 'python':
            return base
        
        base.pop('serializer')
        base['annotation'] = base['annotation'].__name__

        if isinstance(base['default'], NotSet):
            base.pop('default')

        return base

DEFAULT_SERIALIZER: Final[Callable[[Any], str]] = lambda x: str(x)

def FieldSetter[T: Any](
    parts: Iterable[str] | str, 
    serializer: Field[T].SerializerType = DEFAULT_SERIALIZER,
    default: Field[T].Default = NOT_SET,
    annotation: Field[T].TypeAnnotation = NOT_SET,
):
    parts = [parts] if isinstance(parts, str) else parts

    result = Field[T](
        parts=parts,
        annotation=annotation,
        cls=None,
        serializer=serializer,
        default=default
    )

    return cast(T, result)

type AnyField = Field[object]
