# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Value conversion between the storage representation and the annotated types.

``correct_type`` turns raw loaded values (usually ``str``) into the
annotated type of the member. ``to_storage_string`` turns supported values
into their string form, which string-oriented storages need in Python.

Supported scalar types: bool, int, float, complex, str, bytes/bytearray,
enums, dates/times/timedeltas, Decimal, Fraction, UUID, Path, ZoneInfo, and
the ipaddress objects. The secret wrappers
:class:`~advexp.settings_base.secret_str.SecretStr` and
:class:`~advexp.settings_base.secret_bytes.SecretBytes` are also supported:
a loaded string or byte payload is wrapped, and the storage form is the
plain payload.

``Literal`` and ``Union`` annotations are supported as well, together with
the common collection types (list/set/frozenset/tuple/dict, their
``collections.abc`` abstractions, and ``OrderedDict``, nested to any depth)
and dataclasses. A dataclass is stored as a JSON object of its fields, and
it is rebuilt from the annotated class, with each field converted by its own
annotation. All of these types round-trip through the string form and the
JSON storage form. They also round-trip through the TOML and YAML forms,
apart from the values that those forms refuse (see below).

``None`` is a legitimate value to store. It round-trips through the JSON
form (it is kept as ``null``, which is different from a missing key). The
string form and the TOML form have no null, so string-oriented backends and
the TOML backend drop a ``None`` entry instead, and loading falls back to
the default. A ``None`` nested inside a container has no TOML form at all
and is refused.

The TOML form is also stricter than the other forms. Every TOML string is
UTF-8, so bytes payloads that are not UTF-8 text are refused there.
``datetime``, ``date``, and ``time`` values stay native in it (the form that
TOML itself uses), not ISO strings.

The YAML form keeps ``None`` as the null of the document, like the JSON
form. It keeps ``datetime`` and ``date`` values native, like the TOML form,
and it refuses the same text that the TOML form refuses, because every YAML
string is UTF-8. ``time`` values are rendered in their ISO form, because
YAML has no time scalar of its own.
"""

from __future__ import annotations

import collections
import collections.abc
import dataclasses
import datetime
import decimal
import enum
import fractions
import ipaddress
import json
import pathlib
import re
import types
import typing
import uuid
import zoneinfo
from typing import Any, Callable, Dict, Optional, Tuple

from advexp.settings_base.library_configuration import logger_for
from advexp.settings_base.secret_bytes import SecretBytes
from advexp.settings_base.secret_str import SecretStr
from advexp.settings_base.type_display import type_display

# the dataclass-annotation diagnostic is the machinery's own: it carries no
# per-class context down here, so it is carried by the base channel
_logger = logger_for(None)

_TRUE_STRINGS = frozenset(("true", "1", "yes", "on"))
_FALSE_STRINGS = frozenset(("false", "0", "no", "off"))

_DATETIME_TYPES = (datetime.datetime, datetime.date, datetime.time, datetime.timedelta)

_UnionType = getattr(types, "UnionType", None)

_LIST_ORIGINS = (
    list,
    collections.abc.Sequence,
    collections.abc.MutableSequence,
    collections.abc.Iterable,
    collections.abc.Collection,
)
_SET_ORIGINS = (set, collections.abc.Set, collections.abc.MutableSet)
_DICT_ORIGINS = (
    dict,
    collections.OrderedDict,
    collections.abc.Mapping,
    collections.abc.MutableMapping,
)
_BARE_CONTAINERS = (list, tuple, set, frozenset, dict, collections.OrderedDict)

_IPADDRESS_TYPES = (
    ipaddress.IPv4Address,
    ipaddress.IPv6Address,
    ipaddress.IPv4Network,
    ipaddress.IPv6Network,
    ipaddress.IPv4Interface,
    ipaddress.IPv6Interface,
)

# matches what datetime.timedelta.isoformat() emits: "[-][D days, ]H:MM:SS[.ffffff]"
_TIMEDELTA_ISO = re.compile(
    r"^(?P<sign>-)?(?:(?P<days>\d+) days?, )?"
    r"(?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2})(?:\.(?P<micros>\d{1,6}))?$"
)


def _unwrap_optional(annotation: Any) -> Any:
    if annotation is None:
        return None
    origin = typing.get_origin(annotation)
    if origin is typing.Union or (_UnionType is not None and origin is _UnionType):
        args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _unwrap_annotated(annotation: Any) -> Any:
    while typing.get_origin(annotation) is typing.Annotated:
        annotation = typing.get_args(annotation)[0]
    return annotation


def unwrap_annotation(annotation: Any) -> Any:
    """Strip the ``Annotated`` and ``Optional`` wrappers from an annotation.

    This is the shape that :func:`correct_type` dispatches on: ``None`` stays
    ``None``, ``Optional[X]`` collapses to ``X``, and everything else is
    returned as it is.
    """
    return _unwrap_optional(_unwrap_annotated(annotation))


def _json_decode_if_possible(value: Any) -> Any:
    if not isinstance(value, (str, bytes, bytearray)):
        return value
    text = value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else value
    if not text:
        return value
    if text.lstrip().startswith(("{", "[")):
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            pass
    return value


def _collect_generic_args(annotation: Any) -> tuple[Any, ...]:
    origin = typing.get_origin(annotation)
    if origin is not None:
        return typing.get_args(annotation)
    return ()


def _convert_list_like(
    value: Any, annotation: Any, factory: type, convert_items: bool = True
) -> Any:
    if isinstance(value, str):
        decoded = _json_decode_if_possible(value)
        if isinstance(decoded, (list, tuple, set, frozenset)):
            value = decoded
    if isinstance(value, (list, tuple, set, frozenset)):
        item_type = _collect_generic_args(annotation)
        if convert_items and item_type:
            # items are converted even when the container already has the
            # right type: a JSON document yields a list of raw strings for
            # List[datetime] and similar annotations
            subtype = item_type[0]
            return factory(correct_type(item, subtype) for item in value)
        return value if isinstance(value, factory) else factory(value)
    raise ValueError(f"cannot convert {value!r} to {type_display(annotation)}")


def _parse_timedelta_iso(text: str) -> Any:
    """Parse the ``str(timedelta)`` form; ``None`` when it does not match."""
    match = _TIMEDELTA_ISO.match(text.strip())
    if match is None:
        return None
    parts = match.groupdict()
    days = int(parts["days"] or 0)
    negate_rest = False
    if parts["sign"]:
        if days:
            days = -days  # str() prints the minus on the day component only
        else:
            negate_rest = True
    delta = datetime.timedelta(
        days=days,
        hours=int(parts["hours"]),
        minutes=int(parts["minutes"]),
        seconds=int(parts["seconds"]),
        microseconds=int((parts["micros"] or "0").ljust(6, "0")),
    )
    return -delta if negate_rest else delta


def _convert_literal(value: Any, annotation: Any) -> Any:
    for literal in typing.get_args(annotation):
        try:
            converted = correct_type(value, type(literal))
        except (TypeError, ValueError):
            continue
        if converted == literal:
            return converted
    raise ValueError(f"cannot convert {value!r} to {type_display(annotation)}")


def _convert_union(value: Any, annotation: Any) -> Any:
    for arg in typing.get_args(annotation):
        if arg is type(None):
            continue
        try:
            return correct_type(value, arg)
        except (TypeError, ValueError):
            continue
    raise ValueError(f"cannot convert {value!r} to {type_display(annotation)}")


def _convert_dict_like(value: Any, annotation: Any, factory: type = dict) -> Any:
    if isinstance(value, dict):
        data = value
    elif isinstance(value, str):
        decoded = _json_decode_if_possible(value)
        if isinstance(decoded, dict):
            data = decoded
        else:
            raise ValueError(f"cannot convert {value!r} to {type_display(annotation)}")
    else:
        raise ValueError(f"cannot convert {value!r} to {type_display(annotation)}")

    args = _collect_generic_args(annotation)
    if len(args) == 2:
        key_type, value_type = args
        return factory(
            (correct_type(key, key_type), correct_type(item, value_type))
            for key, item in data.items()
        )
    return factory(data)


def _is_dataclass_type(annotation: Any) -> bool:
    return isinstance(annotation, type) and dataclasses.is_dataclass(annotation)


def _is_dataclass_instance(value: Any) -> bool:
    return dataclasses.is_dataclass(value) and not isinstance(value, type)


_unresolved_fields_reported: typing.Set[type] = set()
"""Dataclasses already reported for unresolvable field annotations (warn once)."""


def _resolve_field_annotation(cls: type, name: str, raw: Any) -> Any:
    """Evaluate one string annotation in the namespace of the dataclass's module."""
    if not isinstance(raw, str):
        return raw
    probe = type("_probe", (), {"__annotations__": {name: raw}, "__module__": cls.__module__})
    return typing.get_type_hints(probe)[name]


def _dataclass_fields(source: Any) -> tuple:
    """``dataclasses.fields`` behind an ``Any`` parameter.

    The callers pass classes that ``is_dataclass`` has checked at runtime. The
    static stub of ``fields`` cannot see this, and it demands the
    ``DataclassInstance`` protocol, which a plain ``type`` does not satisfy.
    """
    return dataclasses.fields(source)


def _dataclass_field_types(cls: type) -> Dict[str, Any]:
    # (a user annotation may raise anything when evaluated)
    # noinspection PyBroadException
    try:
        return dict(typing.get_type_hints(cls))
    except Exception:  # noqa: BLE001 - some annotation is unresolvable; go field by field
        pass
    field_types: Dict[str, Any] = {}
    unresolved = []
    for field in _dataclass_fields(cls):
        # (the same evaluation hazard as above, per single annotation)
        # noinspection PyBroadException
        try:
            field_types[field.name] = _resolve_field_annotation(cls, field.name, field.type)
        except Exception:  # noqa: BLE001 - e.g. a class local to a function
            field_types[field.name] = None  # correct_type passes the value through
            unresolved.append(field.name)
    if unresolved and cls not in _unresolved_fields_reported:
        _unresolved_fields_reported.add(cls)
        _logger.warning(
            "cannot resolve the annotations of fields %s of dataclass %s.%s. These fields "
            "are loaded without type conversion (a nested dataclass stays a dict). "
            "String annotations must be resolvable from the module where the "
            "dataclass is defined",
            unresolved,
            cls.__module__,
            cls.__qualname__,
        )
    return field_types


def _convert_dataclass(value: Any, annotation: type) -> Any:
    if isinstance(value, annotation):
        return value
    data: Any = value
    if isinstance(value, (str, bytes, bytearray)):
        # a JSON document is decoded for the fields, while the error
        # messages keep naming the value as stored — the form the reader
        # of the message gave and can compare with the storage
        data = _json_decode_if_possible(value)
    if not isinstance(data, dict):
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    field_types = _dataclass_field_types(annotation)
    kwargs: Dict[str, Any] = {}
    for field in _dataclass_fields(annotation):
        if not field.init:
            continue
        if field.name in data:
            kwargs[field.name] = correct_type(data[field.name], field_types.get(field.name))
        elif field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING:
            raise ValueError(
                f"cannot convert {value!r} to {annotation.__name__}: missing field {field.name!r}"
            )
    # keys the class no longer declares are ignored, so a stored object
    # survives a field being dropped from the dataclass
    try:
        return annotation(**kwargs)
    except TypeError as error:
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}") from error


def correct_type(value: Any, annotation: Any) -> Any:
    """Convert a raw loaded value to the annotated type.

    Raises ``ValueError`` when the value cannot be represented in the
    target type; the pipeline then falls back to the setting default.
    """
    if value is None or annotation is None:
        return value

    annotation = _unwrap_annotated(annotation)
    annotation = _unwrap_optional(annotation)
    if annotation is None:
        return value

    origin = typing.get_origin(annotation)
    if origin is None and annotation in _BARE_CONTAINERS:
        origin = annotation

    if origin is not None:
        if origin is typing.Literal:
            return _convert_literal(value, annotation)
        if origin is typing.Union or (_UnionType is not None and origin is _UnionType):
            return _convert_union(value, annotation)
        if origin is tuple:
            # items are converted per-position below, not by the shared list path
            items = list(_convert_list_like(value, annotation, list, convert_items=False))
            args = _collect_generic_args(annotation)
            if args and args[0] is not Ellipsis:
                item_types = list(args)
                if len(item_types) == 2 and item_types[1] is ...:
                    item_types = [item_types[0]]
                converted = [
                    correct_type(item, item_type) for item, item_type in zip(items, item_types)
                ]
                if len(converted) != len(items):
                    converted = [correct_type(item, item_types[0]) for item in items]
                return tuple(converted)
            return tuple(items)
        if origin is frozenset:
            return _convert_list_like(value, annotation, frozenset)
        if origin in _SET_ORIGINS:
            return _convert_list_like(value, annotation, set)
        if origin in _LIST_ORIGINS:
            return _convert_list_like(value, annotation, list)
        if origin in _DICT_ORIGINS:
            factory = collections.OrderedDict if origin is collections.OrderedDict else dict
            return _convert_dict_like(value, annotation, factory)

    if _is_dataclass_type(annotation):
        return _convert_dataclass(value, annotation)

    if isinstance(annotation, type) and issubclass(annotation, (SecretStr, SecretBytes)):
        if isinstance(value, annotation):
            return value
        if issubclass(annotation, SecretBytes):
            if isinstance(value, str):
                value = value.encode("utf-8", errors="surrogateescape")
            if isinstance(value, (bytes, bytearray)):
                return annotation(bytes(value))
        elif isinstance(value, str):
            return annotation(value)
        # the value stays out of the message whatever it was: a secret
        # member's failed payloads are not for logs either
        raise ValueError(f"cannot convert the <secret> value to {annotation.__name__}")

    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        if isinstance(value, annotation):
            return value
        if isinstance(value, str):
            if value in annotation.__members__:
                return annotation[value]
            try:
                return annotation(int(value))
            except ValueError:
                raise ValueError(
                    f"cannot convert {value!r} to enum {annotation.__name__}"
                ) from None
        if isinstance(value, int) and not isinstance(value, bool):
            return annotation(value)
        raise ValueError(f"cannot convert {value!r} to enum {annotation.__name__}")

    if annotation is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip().lower()
            if text in _TRUE_STRINGS:
                return True
            if text in _FALSE_STRINGS:
                return False
        if isinstance(value, int) and not isinstance(value, bool):
            return bool(value)
        raise ValueError(f"cannot convert {value!r} to bool")

    if annotation in (int, float, complex):
        if type(value) is annotation:
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float, str, complex)):
            raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")
        if annotation is complex:
            if isinstance(value, str):
                return complex(value.strip())
            return complex(value)
        return annotation(value)

    if annotation is str:
        return value if isinstance(value, str) else str(value)

    if annotation in (bytes, bytearray):
        if isinstance(value, annotation):
            return value
        if isinstance(value, str):
            payload = value.encode("utf-8", errors="surrogateescape")
            return payload if annotation is bytes else bytearray(payload)
        if isinstance(value, (bytearray, bytes)):
            return bytes(value) if annotation is bytes else bytearray(value)
        if isinstance(value, (list, tuple)):
            payload = bytes(value)
            return payload if annotation is bytes else bytearray(payload)
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is datetime.date:
        if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
            return value
        if isinstance(value, datetime.datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return datetime.date.fromisoformat(value)
            except ValueError:
                try:
                    # an ISO datetime string truncates to its date part
                    return datetime.datetime.fromisoformat(value).date()
                except ValueError:
                    raise ValueError(f"cannot convert {value!r} to date") from None
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is datetime.datetime:
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                raise ValueError(f"cannot convert {value!r} to datetime") from None
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is datetime.time:
        if isinstance(value, datetime.time):
            return value
        if isinstance(value, str):
            try:
                return datetime.time.fromisoformat(value)
            except ValueError:
                raise ValueError(f"cannot convert {value!r} to time") from None
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is datetime.timedelta:
        if isinstance(value, datetime.timedelta):
            return value
        if isinstance(value, (int, float)):
            return datetime.timedelta(seconds=float(value))
        if isinstance(value, str):
            parsed = _parse_timedelta_iso(value)
            if parsed is not None:
                return parsed
            try:
                return datetime.timedelta(seconds=float(value))
            except ValueError:
                raise ValueError(f"cannot convert {value!r} to timedelta") from None
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation in _DATETIME_TYPES:
        if isinstance(value, annotation):
            return value
        if isinstance(value, str):
            parse: Optional[Callable[[str], Any]] = getattr(annotation, "fromisoformat", None)
            if parse is not None:
                # (the checker does not narrow the getattr result past the check)
                # noinspection PyCallingNonCallable
                return parse(value)
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is decimal.Decimal:
        if isinstance(value, decimal.Decimal):
            return value
        if isinstance(value, (int, float, str)):
            try:
                return decimal.Decimal(str(value))
            except decimal.InvalidOperation:
                raise ValueError(f"cannot convert {value!r} to Decimal") from None
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        if isinstance(value, str):
            return uuid.UUID(value)
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is pathlib.Path:
        if isinstance(value, pathlib.Path):
            return value
        if isinstance(value, str):
            return pathlib.Path(value)
        if isinstance(value, (bytes, bytearray)):
            # the bytes round-trip form of to_json_value: surrogateescape text
            return pathlib.Path(value.decode("utf-8", errors="surrogateescape"))
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation in _IPADDRESS_TYPES:
        if isinstance(value, annotation):
            return value
        if isinstance(value, str):
            try:
                return annotation(value)
            except ValueError as error:
                raise ValueError(f"cannot convert {value!r} to {annotation.__name__}") from error
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is fractions.Fraction:
        if isinstance(value, fractions.Fraction):
            return value
        if isinstance(value, decimal.Decimal):
            return fractions.Fraction(value)
        if isinstance(value, (int, str)):
            return fractions.Fraction(value)
        if isinstance(value, float):
            return fractions.Fraction(str(value))
        raise ValueError(f"cannot convert {value!r} to {annotation.__name__}")

    if annotation is zoneinfo.ZoneInfo:
        if isinstance(value, zoneinfo.ZoneInfo):
            return value
        if isinstance(value, str):
            try:
                return zoneinfo.ZoneInfo(value)
            except Exception as error:  # missing key or broken tz database
                raise ValueError(f"cannot convert {value!r} to ZoneInfo") from error
        raise ValueError(f"cannot convert {value!r} to ZoneInfo")

    # anything else: pass through as loaded
    return value


_PASS_THROUGH_PROBE = object()
"""A unique marker value for :func:`is_pass_through`'s round trip."""


def is_pass_through(annotation: Any) -> bool:
    """Return whether :func:`correct_type` validates anything for this annotation.

    Annotations outside the conversion contract (custom classes, ``Any``,
    unresolvable strings) reach the pass-through tail of ``correct_type`` and
    come back unchanged, so nothing in the conversion constrains their values.
    This probe tells the two kinds of annotations apart without duplicating the
    dispatch. A unique marker object is run through ``correct_type`` in full,
    and only a pass-through annotation can return it as the same object:
    annotations that are inside the contract either transform the marker or
    reject it.
    """
    try:
        return correct_type(_PASS_THROUGH_PROBE, annotation) is _PASS_THROUGH_PROBE
    except (TypeError, ValueError):
        return False


def container_spec(annotation: Any) -> Optional[Tuple[str, Tuple[Any, ...]]]:
    """Classify a container annotation for element-level checks.

    The result is the kind of the container and the annotations of its element
    positions:

    - ``("sequence", (item_type,))`` for list/set/frozenset (a variadic
      ``Tuple[X, ...]`` included);
    - ``("tuple", (first, second, ...))`` for a fixed-length tuple;
    - ``("mapping", (key_type, value_type))`` for dict-like containers;
    - ``None`` for anything that is not a container annotation.

    Bare containers come back with empty positions, because nothing is declared
    inside them that could be checked.
    """
    origin = typing.get_origin(annotation)
    if origin is None and annotation in _BARE_CONTAINERS:
        origin = annotation
    if origin is None:
        return None
    args = typing.get_args(annotation)
    if origin is tuple:
        if args and args[-1] is Ellipsis:
            return ("sequence", (args[0],))
        return ("tuple", tuple(args))
    if origin is frozenset or origin in _SET_ORIGINS:
        return ("sequence", tuple(args[:1]))
    if origin in _LIST_ORIGINS:
        return ("sequence", tuple(args[:1]))
    if origin in _DICT_ORIGINS:
        return ("mapping", tuple(args[:2]))
    return None


def is_secret_type(annotation: Any) -> bool:
    """Whether the annotation wraps its values in a secret type."""
    annotation = unwrap_annotation(annotation)
    return isinstance(annotation, type) and issubclass(annotation, (SecretStr, SecretBytes))


def unwrap_secret(value: Any) -> Any:
    """Return the plain form of a secret wrapper; any other value is returned as it
    is.

    The save path hands this plain form to the serializers, and the value-form
    helpers apply it first. This way the storages keep their plain string and
    bytes contracts and know nothing about the wrappers.
    """
    if isinstance(value, (SecretStr, SecretBytes)):
        return value.get_secret_value()
    return value


def to_storage_string(value: Any) -> str:
    """Render a value for a string-oriented storage (environment variables and
    similar storages).

    The result round-trips with :func:`correct_type`: bools as
    ``True``/``False``, dates and times in ISO format, enums by member name, and
    collections and values such as bytes in a JSON-encoded form. A secret
    wrapper is rendered as its plain payload: the storage form keeps no mask.
    """
    value = unwrap_secret(value)
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="surrogateescape")
    if isinstance(value, bytearray):
        return bytes(value).decode("utf-8", errors="surrogateescape")
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float, complex)):
        return str(value)
    if isinstance(value, (list, tuple, set, frozenset, dict)) or _is_dataclass_instance(value):
        return json.dumps(to_json_value(value), ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, decimal.Decimal):
        # (Decimal defines __str__; the checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, pathlib.Path):
        return str(value)
    if isinstance(value, fractions.Fraction):
        return str(value)
    if isinstance(value, _IPADDRESS_TYPES):
        # (the ipaddress types define __str__; the checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        return str(value)
    if isinstance(value, zoneinfo.ZoneInfo):
        return value.key
    if isinstance(value, datetime.timedelta):
        return str(value)  # timedelta has no isoformat(); str() is the same H:MM:SS form
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    raise TypeError(f"cannot store {type(value).__name__!r} value in a string-based storage")


def to_json_value(value: Any) -> Any:
    """Render a value for a JSON document (the storage form of the JSON backend).

    The result round-trips with :func:`correct_type`: enums by member name,
    dates and times in ISO format, and collections and values that JSON can
    hold. A secret wrapper is rendered as its plain payload: the storage form
    keeps no mask (the recursion carries this into containers and dataclass
    fields).
    """
    value = unwrap_secret(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, complex):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="surrogateescape")
    if isinstance(value, bytearray):
        return bytes(value).decode("utf-8", errors="surrogateescape")
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, datetime.timedelta):
        return str(value)  # timedelta has no isoformat(); str() is the same H:MM:SS form
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        # (Decimal defines __str__; the checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        return str(value)
    if isinstance(value, fractions.Fraction):
        return str(value)
    if isinstance(value, _IPADDRESS_TYPES):
        # (the ipaddress types define __str__; the checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        return str(value)
    if isinstance(value, zoneinfo.ZoneInfo):
        return value.key
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, pathlib.Path):
        return str(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_json_value(item) for key, item in value.items()}
    if _is_dataclass_instance(value):
        return {
            field.name: to_json_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    raise TypeError(f"cannot store {type(value).__name__!r} value in a JSON document")


def _toml_text(text: str) -> str:
    """Return the TOML form of one string value; it is ``text`` itself if it fits.

    Every TOML string is UTF-8 text, and a lone surrogate has no TOML string
    form. The surrogate-escaped decode of a bytes payload (the round-trip form
    that string storages use) contains one whenever the payload was not UTF-8,
    and a ``str`` value may also contain one. Both are refused here, at the
    boundary of the value itself. Otherwise, the write of the whole document
    would fail later with an encoding error that names no setting.
    """
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TypeError(
            "cannot store non-UTF-8 text in a TOML document: a TOML string is always UTF-8"
        ) from exc
    return text


def to_toml_value(value: Any) -> Any:
    """Render a value for a TOML document (the storage form of the TOML backend).

    The result round-trips with :func:`correct_type`: enums by member name,
    timedeltas in their ``str()`` form, collections and dataclasses as arrays
    and tables, and ``datetime``/``date``/``time`` values native (the form that
    TOML itself uses, not ISO strings). A secret wrapper is rendered as its
    plain payload: the storage form keeps no mask (the recursion carries this
    into containers and dataclass fields).

    Two kinds of values have no TOML form and raise ``TypeError``:

    - ``None``. TOML has no null, so the backend removes the whole entry
      instead. Only a ``None`` that is nested in a container reaches this
      refusal.
    - Text or bytes that a TOML string cannot hold (every TOML string is
      UTF-8).
    """
    value = unwrap_secret(value)
    if value is None:
        raise TypeError("cannot store None in a TOML document: TOML has no null")
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _toml_text(value)
    if isinstance(value, complex):
        return _toml_text(str(value))
    if isinstance(value, bytes):
        return _toml_text(value.decode("utf-8", errors="surrogateescape"))
    if isinstance(value, bytearray):
        return _toml_text(bytes(value).decode("utf-8", errors="surrogateescape"))
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, datetime.timedelta):
        return str(value)  # timedelta has no isoformat(); str() is the same H:MM:SS form
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value  # native in TOML — no ISO string encoding
    if isinstance(value, decimal.Decimal):
        # (Decimal defines __str__; the checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        return str(value)
    if isinstance(value, fractions.Fraction):
        return str(value)
    if isinstance(value, _IPADDRESS_TYPES):
        # (the ipaddress types define __str__; the checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        return str(value)
    if isinstance(value, zoneinfo.ZoneInfo):
        return value.key
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, pathlib.Path):
        return str(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_toml_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_toml_value(item) for key, item in value.items()}
    if _is_dataclass_instance(value):
        return {
            field.name: to_toml_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    raise TypeError(f"cannot store {type(value).__name__!r} value in a TOML document")


def _yaml_text(text: str) -> str:
    """Return the YAML form of one string value; it is ``text`` itself if it fits.

    Every YAML string is UTF-8 text, and a lone surrogate has no YAML string
    form. The surrogate-escaped decode of a bytes payload (the round-trip form
    that string storages use) contains one whenever the payload was not UTF-8,
    and a ``str`` value may also contain one. Both are refused here, at the
    boundary of the value itself. Otherwise, the write of the whole document
    would fail later with an encoding error that names no setting.
    """
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise TypeError(
            "cannot store non-UTF-8 text in a YAML document: a YAML string is always UTF-8"
        ) from exc
    return text


def to_yaml_value(value: Any) -> Any:
    """Render a value for a YAML document (the storage form of the YAML backend).

    The result round-trips with :func:`correct_type`: enums by member name,
    timedeltas in their ``str()`` form, collections and dataclasses as
    sequences and mappings, and ``datetime``/``date`` values native (the forms
    that YAML itself uses, not ISO strings). ``time`` values are rendered in
    their ISO form, because YAML has no time scalar of its own.

    ``None`` stays ``None`` (YAML has a null), so a ``None`` value is stored and
    not dropped. A secret wrapper is rendered as its plain payload: the storage
    form keeps no mask (the recursion carries this into containers and
    dataclass fields).

    One kind of value has no YAML form and raises ``TypeError``: text or bytes
    that a YAML string cannot hold (every YAML string is UTF-8).
    """
    value = unwrap_secret(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _yaml_text(value)
    if isinstance(value, complex):
        return _yaml_text(str(value))
    if isinstance(value, bytes):
        return _yaml_text(value.decode("utf-8", errors="surrogateescape"))
    if isinstance(value, bytearray):
        return _yaml_text(bytes(value).decode("utf-8", errors="surrogateescape"))
    if isinstance(value, enum.Enum):
        return value.name
    if isinstance(value, datetime.timedelta):
        return str(value)  # timedelta has no isoformat(); str() is the same H:MM:SS form
    if isinstance(value, datetime.datetime):
        return value  # native in YAML — no ISO string encoding
    if isinstance(value, datetime.date):
        return value  # native in YAML — no ISO string encoding
    if isinstance(value, datetime.time):
        return _yaml_text(value.isoformat())  # YAML carries no time scalar
    if isinstance(value, decimal.Decimal):
        # (Decimal defines __str__; the checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        return _yaml_text(str(value))
    if isinstance(value, fractions.Fraction):
        return _yaml_text(str(value))
    if isinstance(value, _IPADDRESS_TYPES):
        # (the ipaddress types define __str__; the checker's stub view says otherwise)
        # noinspection PyStringConversionWithoutDunderMethod
        return _yaml_text(str(value))
    if isinstance(value, zoneinfo.ZoneInfo):
        return _yaml_text(value.key)
    if isinstance(value, uuid.UUID):
        return _yaml_text(str(value))
    if isinstance(value, pathlib.Path):
        return _yaml_text(str(value))
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_yaml_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_yaml_value(item) for key, item in value.items()}
    if _is_dataclass_instance(value):
        return {
            field.name: to_yaml_value(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    raise TypeError(f"cannot store {type(value).__name__!r} value in a YAML document")
