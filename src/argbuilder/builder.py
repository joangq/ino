from __future__ import annotations

import json
import subprocess
from .field import DEFAULT_SERIALIZER, Field, AnyField, NOT_SET, VALUE_TOKEN
from .exception import InvalidFieldError
from typing import Any, Callable, Literal, Self, cast, dataclass_transform, overload
from operator import add
from functools import reduce as foldl
from warnings import deprecated
from .field import FieldSetter
from ._color import Color
from pathlib import Path

FROM_DICT_DEPRECATION = deprecated("""\
This method is deprecated from the public API.
Use load/loads to load from a dump.
Or use '_from_dict' to explicitly reference the private API.
""")

DISPLAY_DEPRECATION = deprecated("_display is no longer supported and will be removed in a future version.")

def is_json_serializable(x: object) -> bool:
    if isinstance(x, Command):
        return True

    # simple types
    if isinstance(x, (int, float, bool, str)):
        return True

    # list/tuple
    if isinstance(x, (list, tuple)):
        return all(is_json_serializable(y) for y in x)

    # dict
    if isinstance(x, dict):
        return all(
            is_json_serializable(k) and is_json_serializable(v)
            for k,v in x.items()
        )

    return False

def JsonEncoderFactory(
    options: dict[str, Any],
    base_encoder: type[json.JSONEncoder] = json.JSONEncoder,
):
    class JsonEncoder(base_encoder):
        def default(self, o: object) -> object:
            if isinstance(o, Command):
                return o.dump(mode='json', **options)
            return super().default(o)

    return JsonEncoder

def find_all(
        x: str,
        sub: str,
        start: int = 0,
        indices: list[int] | None = None
) -> list[int]:
    if indices is None:
        indices = []

    index = x.find(sub, start)

    if index == -1:
        return indices

    indices.append(index)
    return find_all(x, sub, index + len(sub), indices)

def split_by(x: str, sub: str) -> list[str]:
    indices = find_all(x, sub)
    n = len(sub)

    parts = list[str]()
    last = 0

    for left in indices:
        right = left + n

        if last < left:
            parts.append(x[last:left])

        parts.append(x[left:right])
        last = right

    if last < len(x):
        parts.append(x[last:])

    return parts


def get_command_name(x: object|type) -> str:
    if not isinstance(x, type):
        return get_command_name(type(x))
    else:
        name = x.__name__
        if '_' not in name:
            result = name
        else:
            result = name.rsplit('_', 1)[1]

        return result.lower()

class Chainable:
    _parent: 'Chainable | None'

    def __init__(self, **kwargs: object):
        self._parent = None
        self._data = kwargs

    def __getattribute__(self, name: str) -> 'Bound|Any':
        try:
            attr = super().__getattribute__(name)
        except AttributeError:
            raise

        if isinstance(attr, type) and issubclass(attr, Chainable):
            return Bound(cast(type[Command], attr), self)

        return cast(Any, attr)

# ==============================================================================


def bool_serializer[T](f: Field[T]):
    def _(value: T) -> list[str]:
        if isinstance(f.parts, str):
            result: list[str] = [f.parts] if value else []
        else:
            result = list(f.parts) if value else []
        return result
    return _

def path_serializer[T](f: Field[T]):
    def _(value: T):  # Returns str for format substitution; Iterable[str] for type
        if not isinstance(value, Path):
            raise TypeError(f'Path field {value} must be of type {Path}, but got {type(value).__name__}')
        return str(Path(value).resolve())
    return _

def command_serializer[T](f: Field[T]):
    def _(value: T):
        if not isinstance(value, Command) or not issubclass(type(value), Command):
            raise TypeError(f'Command field {value} must be of type Command, but got {type(value).__name__}')

        return value.build()
    return _

SERIALIZERS = {
    bool: bool_serializer,
    Path: path_serializer,
}

# ==============================================================================

@dataclass_transform(field_specifiers=(FieldSetter, Field,))
class Command(Chainable):
    __builder_fields__: dict[str, AnyField]

    arg0: str | Callable[..., str] = lambda self: get_command_name(type(self))

    def __init_subclass__(cls):
        annotations = cls.__annotations__

        builder_fields = dict[str, AnyField]()
        for k,v in cls.__dict__.items():
            if not isinstance(v, Field):
                continue

            v = cast(AnyField, v)

            if v.annotation is not NOT_SET:
                annotations[k] = v.annotation


            if k not in annotations:
                raise InvalidFieldError(f'Field {k} is Field but has no type annotation.')

            t = annotations[k]
            if (v.serializer is DEFAULT_SERIALIZER):
                predefined_serializer = SERIALIZERS.get(t, None)
                if predefined_serializer is not None:
                    v.serializer = predefined_serializer(v)

            v.cls = cls
            v.annotation = annotations[k]
            builder_fields[k] = v

        cls.__builder_fields__ = builder_fields

    def fields(self):
        return {
            k:v
            for k,v in self.__dict__.items()
            if k in self.class_fields()
        }

    @classmethod
    def class_fields(cls):
        return cls.__builder_fields__

    def __init__(self, **kwargs: object):
        super().__init__()
        defaults = {
            k:v.default
            for k,v in self.class_fields().items()
            if v.default is not NOT_SET
        }

        kwargs = (defaults|kwargs)
        for k,v in kwargs.items():
            if k not in self.class_fields():
                raise KeyError(f'{k} is not a valid parameter.')
            setattr(self, k, v)

    def __repr__(self):
        cls = type(self)
        fields = ', '.join(f'{k}={v}' for k,v in self.fields().items())
        return f'{cls.__name__}({fields})'

    def _get_arg0(self) -> str:
        arg0 = getattr(type(self), 'arg0')

        result = None
        if isinstance(arg0, str):
            result = arg0
        elif callable(arg0):
            result = arg0(self)
        else:
            raise TypeError(
                f"'arg0' can be of type either 'str' or '(self) -> str', but got '{type(arg0).__name__}'"
            )

        assert result is not None
        return cast(str, result)

    @classmethod
    def _from_dict(cls, data: dict[str, object]):
        params = {
            k:v
            for k,v in data.items()
            if k in cls.__builder_fields__
        }

        return cls(**params)

    @classmethod
    @FROM_DICT_DEPRECATION
    def from_dict(cls, data: dict[str, object]):
        return cls._from_dict(data)

    def _build_fields(self, with_self: bool, extra: dict[str, str]):
        result = list[str]()
        for k,v in self.fields().items():
            field = self.class_fields()[k]
            value = field.serializer(v)

            if not value:
                continue

            if isinstance(value, str):
                strings = [field.parts] if isinstance(field.parts, str) else field.parts
                result.extend((s.format(value=value) for s in strings))
            else:
                if isinstance(field.parts, str):
                    parts = split_by(field.parts, VALUE_TOKEN)
                else:
                    parts = [p for s in field.parts for p in split_by(s, VALUE_TOKEN)]
                for part in parts:
                    if part == VALUE_TOKEN:
                        result.extend(value)
                    else:
                        result.append(part.strip())

        ret = list[str]()

        if with_self:
            ret.append(self._get_arg0())

        ret.extend(result)
        ret.extend(extra)
        #ret = [*result, *args]
        return ret

    def build(self, with_self: bool = True, **args: str):
        has_parent = (
            hasattr(self, '_parent')
            and self._parent is not None
        )

        if has_parent:
            parts = list[Any]()
            node = self
            while node:
                parts.append(node._build_fields(
                    with_self=with_self,
                    extra={},
                ))
                node = node._parent

            return foldl(add, reversed(parts))

        return self._build_fields(
            with_self=with_self,
            extra=args
        )

    def Popen(self, **kwargs: object):
        DEFAULT_KWARGS = dict[str, Any](
            text=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        kwargs = DEFAULT_KWARGS | cast(dict[str, Any], kwargs)

        args = self.build()
        result = subprocess.Popen(args, **cast(Any, kwargs))

        return result

    @DISPLAY_DEPRECATION
    def _display(self, pretty: bool, short: bool = True) -> str:
        ...

    @overload
    def run(
        self,
        *,
        text: Literal[True],
        verbose: bool = False,
        **kwargs: object
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def run(
        self,
        *,
        text: Literal[False] = False,
        verbose: bool = False,
        **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]: ...

    def run(
        self,
        text: bool = False,
        verbose: bool = False,
        **kwargs: object
    ):
        """Runs the built command via subprocess.run. Kwargs are passed through."""
        DEFAULT_KWARGS: dict[str, Any] = dict(
            text=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        kwargs = DEFAULT_KWARGS | cast(dict[str, Any], kwargs)
        subprocess_kwargs = {k: v for k, v in kwargs.items() if k not in ('verbose', 'pretty')}

        args = self.build()

        try:
            result = subprocess.run(args, **cast(Any, subprocess_kwargs))
        except FileNotFoundError as e:
            result = subprocess.CompletedProcess(
                args=args,
                returncode=1,
                stdout=b'',
                stderr=f'Error running command: {e}'.encode(),
            )

        return result

    def __eq__(self, other: object):
        if not isinstance(other, type(self)):
            return False

        return (
            self.fields() == other.fields()
            and self.class_fields() == other.class_fields()
        )

    def dump(
        self,
        mode: Literal['json', 'python'] = 'python',
        include_values: bool = True,
        serialize_fields: bool = True,
    ) -> dict:
        fields = []
        for k,v in self.class_fields().items():
            field_dump = v.dump(mode=mode)

            if include_values:
                values = {}
                val = self.fields()[k]
                if mode == 'json' and is_json_serializable(val):
                    values['runtime'] = val

                field_dump['values'] = values

            if serialize_fields:
                field_dump.setdefault('values', {})['serialized'] = \
                    v.serializer(self.fields()[k])
            fields.append({'name': k, **field_dump})

        return {
            'name': self._get_arg0(),
            'fields': fields
        }

    def dump_json(
        self,
        include_values: bool = True,
        serialize_fields: bool = True,

        # json.dumps kwargs
        skipkeys: bool = False,
        ensure_ascii: bool = True,
        check_circular: bool = True,
        allow_nan: bool = True,
        cls: type[json.JSONEncoder] | None = None,
        indent: int | str | None = None,
        separators: tuple[str, str] | None = None,
        default: Callable[[Any], Any] | None = None,
        sort_keys: bool = False,

        **kwargs: Any
    ) -> str:
        json_kwarg_keys = (
            'skipkeys',
            'ensure_ascii',
            'check_circular',
            'allow_nan',
            'cls',
            'indent',
            'separators',
            'default',
            'sort_keys'
        )

        vars_ = locals()

        json_kwargs: dict[str, Any] = {}
        for k in json_kwarg_keys:
            if k in vars_:
                json_kwargs[k] = vars_.pop(k)

        json_kwargs['cls'] = cast(
            type[json.JSONEncoder],
            JsonEncoderFactory(dict(
                include_values=include_values,
                serialize_fields=serialize_fields,
            )),
        )

        dump = self.dump(
            mode='json',
            include_values=include_values,
            serialize_fields=serialize_fields
        )

        return json.dumps(dump, **(json_kwargs | kwargs))

    @classmethod
    def loads(cls, data: str) -> 'Command':
        return cls.load(json.loads(data))

    @classmethod
    def load(cls, data: dict) -> 'Command':
        params = {
            f['name']: f['values']['runtime']
            for f in data.get('fields', [])
            if f.get('name') in cls.class_fields()
            and 'runtime' in f.get('values', {})
        }
        return cls._from_dict(params)

class Bound:
    def __init__(self, cls: type[Command], parent: Chainable):
        self.cls = cls
        self.parent = parent

    def __call__(self, **kwargs: object):
        child = self.cls(**kwargs)
        child._parent = self.parent
        return child

    def _from_dict(self, data: dict[str, object]):
        child = self.cls._from_dict(data)
        child._parent = self.parent
        return child

    @FROM_DICT_DEPRECATION
    def from_dict(self, data: dict[str, object]):
        return self._from_dict(data)

SERIALIZERS[Command] = command_serializer

@deprecated("Deprecated, use 'Command' instead.")
class Builder(Command): ...
