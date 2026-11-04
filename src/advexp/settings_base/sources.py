# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The source chain of a layered class.

A layered class resolves a member by walking its chain of sources in order.
The first link that provides a value wins, the declared default is the
implicit last layer, and a miss moves on down the chain. The chain is
declared once per class, through the ``options=`` keyword of the ``class``
statement:

```python
class AppConfig(Configuration, options=Sources(
    env_source(name_prefix="APP_"),
    json_source(file="app.json"),
)):
```

A single link that is spelled alone is normalized into the one-link chain
of the same class. For example, ``options=json_source(file="app.json")``
reads exactly like the chain above, without the environment link. The two
spellings never mix in one ``options=``: a lone link next to a
``Sources(...)`` makes the ``class`` statement fail, because the order of a
chain that is read out of two shapes is an order that the reader cannot see.

The chain is a metadata entry of the class itself, stored per declaring
class. A subclass without a chain of its own inherits the nearest one above
it. A subclass with its own chain switches to it for itself and its
subclasses only, and the base class keeps reading its own sources.

The read-write package binds its sources in the flat way: one ``*_source``
builder per family, and each builder stores its link under the own metadata
key of the family. These are the source seats that the second half of this
module carries.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Tuple

from advexp.settings_base.context import SettingsContext
from advexp.settings_base.dotenv_file import DOTENV_FILE_METADATA
from advexp.settings_base.json_file import JSON_FILE_METADATA
from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.toml_file import TOML_FILE_METADATA
from advexp.settings_base.yaml_file import YAML_FILE_METADATA

SOURCE_CHAIN_METADATA = "__SourceChain"
"""The class metadata key of the source chain — one key for every
layered class of the family. The value is the :class:`Sources` object
itself; the machinery stores it per declaring class, so inheritance
resolves the nearest chain above a subclass."""

LINK_FILE_PARAM = "file"
"""The link parameter naming the file a file-family link reads. The
file families of both distributions share the spelling: a link's
parameters are the family builders' and serializers' own vocabulary,
and the file families agree on this one. The file may spell template
slots — ``settings-{APP_ENV}.json`` — resolved through the link's
``parameters`` at load time."""

LINK_PARAMETERS_PARAM = "parameters"
"""The link parameter carrying the path parameters of a templated
``file`` — the :class:`~advexp.settings_base.env_parameter.EnvParameter`
results the builder's ``parameters=`` spelled. An untemplated link
carries ``None``; a templated one carries the tuple the builder's
checks left standing, and its serializer unfolds the file through them
on every pass."""

LINK_PATH_PARAM = "path"
"""The link parameter anchoring a link's keys inside a subtree of its
storage — the JSON Pointer subtree of a JSON link, the table path of a
TOML link. The member's own ``path=`` locates its key within the
subtree; the link's path prefixes it and cannot be cancelled, only
escaped by another link over the same storage."""

LINK_NAME_PATTERN_PARAM = "name_pattern"
"""The link parameter spelling the pattern a document family's link
builds its keys with — the full ``{module}.{class}.{member}`` pattern
when the link spells none."""


def check_source_chain(value: Any) -> Optional[str]:
    """Describe why ``value`` is not a valid source chain; return ``None`` if it is
    valid.

    This is the metadata validator of the chain: the value must be a non-empty
    :class:`Sources` object. The runtime channel accepts a rebuilt chain in the
    same way (``set_class_metadata(SOURCE_CHAIN_METADATA, Sources(...))``).
    Anything else (a lone link, a list, a mapping) is a problem that the
    machinery turns into an error that names the class and the key.
    """
    if isinstance(value, Sources):
        if value.links:
            return None
        return "the chain holds no links; declare at least one source"
    return f"must be a Sources chain, got {type(value).__name__}"


class Sources:
    """The source chain of a layered class, in its resolution order.

    It is built from the results of the source builders
    (``Sources(env_source(...), json_source(...))``), and the first link that is
    named is the first one that is read. Iteration returns the links in that
    order. The chain itself is plain data that the load pass walks.

    An empty chain cannot be created: a layered class with nothing to read from
    is a mistake in the declaration, and the ``class`` statement is the place to
    report it.
    """

    def __init__(self, *bindings: SourceBinding) -> None:
        if not bindings:
            raise TypeError(
                "Sources() declares no links. Add at least one source builder "
                "(env_source(...), json_source(...), ...) to the chain"
            )
        links: Tuple[SourceLink, ...] = ()
        for binding in bindings:
            if not isinstance(binding, SourceBinding):
                raise TypeError(
                    "Sources() expects the results of source builders "
                    f"(env_source(...), json_source(...), ...), got {binding!r}"
                )
            links += (binding.link,)
        self.__bindings: Tuple[SourceBinding, ...] = bindings
        self.__links = links

    @property
    def bindings(self) -> Tuple[SourceBinding, ...]:
        """The source builders' results the chain was built from."""
        return self.__bindings

    @property
    def links(self) -> Tuple[SourceLink, ...]:
        """The chain's links, in the order a load reads them."""
        return self.__links

    def __iter__(self) -> Iterator[SourceLink]:
        return iter(self.__links)

    def __len__(self) -> int:
        return len(self.__links)

    def __repr__(self) -> str:
        return f"Sources({', '.join(repr(link) for link in self.__links)})"


def chain_options_entries(
    declaration: Any, family: Optional[str], class_name: str
) -> Dict[str, Any]:
    """Lay out the declaration of one chain as the metadata entries that it stores.

    This is the single step of the metaclass for both spellings. A
    ``Sources(...)`` chain stays as it is under the chain key. A lone source
    builder is normalized into the one-link chain of the same shape. The side
    entries of the builders (for example, the naming of the environment family,
    when a link declares it) are added next to the chain, under their own
    family keys.

    Every binding that the declaration carries must belong to the family of the
    class. A builder of another distribution makes the ``class`` statement fail
    here, and the error names the class and both distributions.
    """
    if isinstance(declaration, SourceBinding):
        chain: Any = Sources(declaration)
        bindings: Tuple[SourceBinding, ...] = (declaration,)
    else:
        chain = declaration
        bindings = declaration.bindings
    for binding in bindings:
        if binding.family is not None and family is not None and binding.family != family:
            raise TypeError(f"{class_name} declares {binding.family} sources in a {family} class")
    entries: Dict[str, Any] = {SOURCE_CHAIN_METADATA: chain}
    for binding in bindings:
        for name, value in binding.extras.items():
            if name in entries:
                raise TypeError(
                    f"{class_name} declares the metadata name(s) {name!r} more than "
                    "once in options=. Declare each name only once"
                )
            entries[name] = value
    return entries


LibraryConfiguration.register_class_metadata_validator(SOURCE_CHAIN_METADATA, check_source_chain)


# -- the source seats of the two-way package ---------------------------------
#
# A settings class binds its storages one builder at a time — no chain,
# no order between the families — and each family's builder stores its
# link under the family's own metadata key below. The seat is flat, not
# per-class: a subclass without its own binding of the family inherits
# the nearest one above it, and a subclass with one switches to it for
# itself and below — the replacement rule of every family binding.

JSON_SOURCE_METADATA = "JSONSettingsSource"
"""The metadata key of the JSON family's source seat. The value is the
family's :class:`~advexp.settings_base.source_link.SourceLink` — its
file, its name pattern, its path parameters — built by the
distribution's ``json_source(...)`` builder."""

TOML_SOURCE_METADATA = "TOMLSettingsSource"
"""The metadata key of the TOML family's source seat; the TOML twin of
:data:`JSON_SOURCE_METADATA`, built by ``toml_source(...)``."""

YAML_SOURCE_METADATA = "YAMLSettingsSource"
"""The metadata key of the YAML family's source seat; the YAML twin of
:data:`JSON_SOURCE_METADATA`, built by ``yaml_source(...)``."""

ENVIRONMENT_SOURCE_METADATA = "EnvironmentSource"
"""The metadata key of the process-environment source seat. The value is
the backend's :class:`~advexp.settings_base.source_link.SourceLink`; the
family's naming rules are not the link's to carry — they live in the
family's own per-class entry beside it, one dictionary for the whole
variable namespace. Built by ``env_source(...)``."""

DOTENV_SOURCE_METADATA = "DotenvSource"
"""The metadata key of the ``.env`` file source seat; the dotenv twin of
:data:`ENVIRONMENT_SOURCE_METADATA`, built by ``dotenv_source(...)``."""

FILE_SEAT_SOURCES: Dict[str, str] = {}
"""The file seats and the source seats they cannot sit beside, family by
family. A family's file seat names the file of the class's family members
when another family's builder holds the binding; beside its own family's
source binding it names one storage twice, and the ``class`` statement
refuses the pair — a bound family's file belongs on its source builder.
The registry fills through :func:`register_file_seat`: the bundled
families register below, and a custom backend that ships a file seat of
its own registers the pair from its plugin module the same way."""

_SOURCE_LINK_KEYS: List[str] = []
"""The registered source seats, in registration order. The bundled
families register theirs below; a custom backend registers its own seat
through :func:`register_source_link_key`, and the passes collect the
links of every registered seat a settings class declares."""


def check_source_link(value: Any) -> Optional[str]:
    """Describe why ``value`` is not a source link; return ``None`` if it is valid.

    This is the validator of the entry of every source seat: the value must be a
    :class:`~advexp.settings_base.source_link.SourceLink`. Anything else (a file
    path, a mapping, ``None``) is a problem that the machinery turns into an
    error that names the settings class and the key.

    The seat has no empty form. A class that is not bound to the family simply
    carries no entry. To unbind a class, remove the entry
    (``delete_class_metadata``) instead of storing a placeholder.
    """
    if isinstance(value, SourceLink):
        return None
    return f"must be a SourceLink, got {type(value).__name__}"


def register_source_link_key(metadata_name: str) -> None:
    """Register the source seat of a family: its metadata key and its validator.

    The key of the seat is the place where the ``*_source`` builder of the
    family stores its link, and where the passes look the link up. Registering
    twice hands the registry the same validator, which is a no-op. This is the
    registration rule for family keys that the metadata registry follows.

    A custom backend calls this function from its plugin module. The import
    alone seats the family, which is the pattern of the bundled families.
    """
    if metadata_name in _SOURCE_LINK_KEYS:
        return
    _SOURCE_LINK_KEYS.append(metadata_name)
    LibraryConfiguration.register_class_metadata_validator(metadata_name, check_source_link)


for _seat in (
    JSON_SOURCE_METADATA,
    TOML_SOURCE_METADATA,
    YAML_SOURCE_METADATA,
    ENVIRONMENT_SOURCE_METADATA,
    DOTENV_SOURCE_METADATA,
):
    register_source_link_key(_seat)


def register_file_seat(file_seat: str, source_seat: str) -> None:
    """Register the file seat of a family, and the source seat that it cannot be
    declared next to.

    The ``class`` statement rejects a declaration that holds both seats of one
    family: the pair would name one storage twice, and the file of a bound
    family belongs on its source builder. This rejection is not a special case
    of the bundled families. It comes from the registry that this function
    fills.

    Registering the same pair again is a no-op, which is the registration rule
    for family keys that the metadata registry follows. The registry refuses a
    conflict in two cases: a file seat that is claimed for another source seat,
    and a pair that names a source seat that no family registered.

    A custom backend calls this function from its plugin module, next to
    :func:`register_source_link_key`, which is the pattern of the bundled
    families.
    """
    if FILE_SEAT_SOURCES.get(file_seat) == source_seat:
        return
    if file_seat in FILE_SEAT_SOURCES:
        raise ValueError(
            f"the file seat {file_seat!r} is already registered for the source "
            f"seat {FILE_SEAT_SOURCES[file_seat]!r}"
        )
    if source_seat not in _SOURCE_LINK_KEYS:
        raise ValueError(
            f"the file seat {file_seat!r} refers to the source seat {source_seat!r}, "
            f"which no family has registered. Register the source seat first "
            f"(register_source_link_key)"
        )
    FILE_SEAT_SOURCES[file_seat] = source_seat


for _seat, _source in (
    (JSON_FILE_METADATA, JSON_SOURCE_METADATA),
    (TOML_FILE_METADATA, TOML_SOURCE_METADATA),
    (YAML_FILE_METADATA, YAML_SOURCE_METADATA),
    (DOTENV_FILE_METADATA, DOTENV_SOURCE_METADATA),
):
    register_file_seat(_seat, _source)


EXCLUSIVE_SOURCE_SEATS: List[str] = []
"""Source seats that cannot sit beside another source seat. The bundled
families' bindings serve their own members and sit side by side freely,
but a storage of the neutral members alone — the mapping storage of the
settings package — has no order to share a class with another binding:
which storage a plain member reads would be the seats' registration
business, not the declaration's. The registry fills through
:func:`register_exclusive_source_seat`: a backend shipping such a
storage registers its seat from its plugin module, and the settings
``class`` statement refuses a class whose bindings hold the seat beside
another one."""


def register_exclusive_source_seat(metadata_name: str) -> None:
    """Register a source seat that must be the only source seat of the class.

    The seat must already be a registered source seat
    (:func:`register_source_link_key`). Registering the same seat again is a
    no-op, which is the registration rule for family keys that the metadata
    registry follows.

    A backend calls this function from its plugin module, next to
    :func:`register_source_link_key`. The import alone makes the seat exclusive,
    which is the pattern of the bundled mapping storage.
    """
    if metadata_name in EXCLUSIVE_SOURCE_SEATS:
        return
    if metadata_name not in _SOURCE_LINK_KEYS:
        raise ValueError(
            f"the seat {metadata_name!r} does not match any registered source seat. "
            f"Register the source seat first (register_source_link_key)"
        )
    EXCLUSIVE_SOURCE_SEATS.append(metadata_name)


def declared_source_links(context: SettingsContext) -> Tuple[SourceLink, ...]:
    """Return the source links that a settings class declares, one seat at a time.

    Every registered seat that the chain of the class holds contributes its
    link. The nearest entry of the key of each family wins, so a subclass
    rebinds a family by declaring its own builder, and keeps the rest.

    The order is the registration order of the seats. A settings class reads no
    chain, so the order only arranges the diagnostics, and it never affects the
    resolution of a member.
    """
    links = []
    for metadata_name in _SOURCE_LINK_KEYS:
        link = context.get_class_metadata(metadata_name)
        if link is not None:
            links.append(link)
    return tuple(links)
