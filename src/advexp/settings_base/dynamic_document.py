# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The dynamic side of a document backend.

A document backend holds the entries in one tree-shaped document. The JSON,
TOML, and YAML file backends of the family are such backends. All of them
serve their dynamic entries through one shared layout. The entries are
stored in a section of the document (one nested object per settings class)
or, if the section is disabled, under flat ``D``-prefixed full-name keys at
the document root. If the class gives the dynamic side a file of its own,
that file is resolved through the same levels, whatever the document
format.

The layout is the storage contract of the family: a file that is written by
the settings distribution can be read back by the configuration
distribution. For this reason, the layout lives here, in shared code, and
not in parallel tests of the two distributions.

The module serves both the plugins and the serializers of the document
backends. It provides the placement of one entry, the enumeration of the
entries of a class, the resolution of the own file of the dynamic side, and
the lookup of the dynamic plugin that is pinned to the attribute class of a
backend. This lookup frees a serializer from importing the plugin class: the
plugin imports the serializer for its binding, so an import in the other
direction at the top level would be circular.
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any, Callable, List, Mapping, NamedTuple, Optional, Sequence, Union

from advexp.settings_base.context import SETTINGS_CONTEXT_ATTR, SettingsContext
from advexp.settings_base.document_dynamic_settings_plugin import (
    _UNSET_SECTION,
    DocumentDynamicSettingsPlugin,
)
from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.module_default import module_default_for
from advexp.settings_base.names import (
    DYNAMIC_SETTING_NAME_PREFIX,
    get_dynamic_setting_full_name,
    get_dynamic_setting_name,
    get_dynamic_settings_class_prefix,
    get_setting_name_delimiter,
)
from advexp.settings_base.pointer import array_index, pointer_display, pointer_steps
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.user_facing_error import UserFacingError

DynamicFileSpelling = Union[str, os.PathLike]
"""A configured file spelling: a path as text or as ``os.PathLike``."""

JSON_DYNAMIC_GROUP_METADATA = "__JSONDynamicSettingsGroup"
"""The class metadata key of the JSON dynamic reader's writer group. The
value is the writing class's group key — the text its entries sit under in
the document — declared beside the reading class's JSON source binding
(``json_source(dynamic_of=...)``); a class without one reads no dynamic
entries."""

TOML_DYNAMIC_GROUP_METADATA = "__TOMLDynamicSettingsGroup"
"""The metadata key of the TOML dynamic reader's writer group; the TOML
twin of :data:`JSON_DYNAMIC_GROUP_METADATA`, declared beside the reading
class's TOML source binding (``toml_source(dynamic_of=...)``)."""

YAML_DYNAMIC_GROUP_METADATA = "__YAMLDynamicSettingsGroup"
"""The metadata key of the YAML dynamic reader's writer group; the YAML
twin of :data:`JSON_DYNAMIC_GROUP_METADATA`, declared beside the reading
class's YAML source binding (``yaml_source(dynamic_of=...)``)."""


def check_dynamic_settings_group(value: Any) -> Optional[str]:
    """Describe why ``value`` is not a writer-group key; return ``None`` if it is
    valid.

    This is the validator of the group metadata keys. The value is the group key
    of the writing class: a non-empty string, which is the name under which the
    entries of the writer are stored (``"app.LocalSettings"`` for a writer class
    with the default name). Anything else (an empty string, a non-string) is a
    problem that the machinery turns into an error that names the class and the
    key.
    """
    if isinstance(value, str) and value:
        return None
    return f"must be a non-empty string (the writing class's group key), got {value!r}"


LibraryConfiguration.register_class_metadata_validator(
    JSON_DYNAMIC_GROUP_METADATA, check_dynamic_settings_group
)
LibraryConfiguration.register_class_metadata_validator(
    TOML_DYNAMIC_GROUP_METADATA, check_dynamic_settings_group
)
LibraryConfiguration.register_class_metadata_validator(
    YAML_DYNAMIC_GROUP_METADATA, check_dynamic_settings_group
)


def document_dynamic_plugin(
    context: SettingsContext, attribute_class: type
) -> Optional[DocumentDynamicSettingsPlugin]:
    """Return the dynamic plugin to which the attribute class of a backend is
    pinned.

    The dynamic plugin of a document backend declares the namespaced pin
    ``DynamicSettingAttribute[<attribute class>]`` as the attribute class of its
    binding. The pin that is built from the attribute class of the backend
    therefore identifies the plugin: it is the first registered plugin whose
    binding matches, either by the namespaced form of the pin or by the bare
    attribute class. The result is ``None`` if no registered plugin serves the
    dynamic side of the backend; importing the plugin module is what enables it.
    A serializer reaches the section parameters through this lookup instead of
    importing the plugin class.
    """
    for plugin_class in LibraryConfiguration.registered_plugin_classes():
        if not issubclass(plugin_class, DocumentDynamicSettingsPlugin):
            continue
        declared = getattr(plugin_class, "binding", None)
        pin = getattr(declared, "attribute_class", None) if declared is not None else None
        if pin is attribute_class or (
            getattr(pin, "pinned_attribute_class", None) is attribute_class
        ):
            return context.get_plugin(plugin_class)
    return None


def resolve_dynamic_document_file(
    context: SettingsContext,
    *,
    dynamic_file_metadata: str,
    module_default_holder: type,
    static_levels: Callable[[], Optional[DynamicFileSpelling]],
) -> Optional[DynamicFileSpelling]:
    """Return the configured spelling of the file of the dynamic entries.

    The resolution order is as follows. First come the own levels of the dynamic
    side: the per-class binding of the class (the nearest one along the settings
    class chain), the declaration of the declaring module, and the module-wide
    value of the holder. If none of them is set, the static levels that the
    caller hands in are used (its source binding, and its own bindings and
    defaults). The default is therefore the file of the static side: one shared
    document.

    The result is ``None`` if no level of either side names a file. The caller
    turns that into its own configuration error.
    """
    binding = context.get_class_metadata(dynamic_file_metadata)
    if binding is not None:
        return binding
    # the holder's parameter read is dynamic: every backend names its own
    # attribute, spelled by the lambda the registry resolves it through
    process_wide: Any = module_default_holder
    declared = module_default_for(
        module_default_holder,
        lambda holder: holder.file_path,
        context.settings_class.__module__,
    )
    if declared is not None:
        return declared
    if process_wide.file_path is not None:
        return process_wide.file_path
    return static_levels()


def dynamic_section_segments(
    context: SettingsContext, plugin: Optional[DocumentDynamicSettingsPlugin]
) -> Optional[List[str]]:
    """Location segments of the dynamic section; ``None`` means flat keys.

    The location is the section name plus, when it is bound, the segments of the
    section path (the ``name=``/``path=`` pair of the dynamic plugin). Each
    parameter resolves along the MRO of the settings class to the most derived
    explicit binding, and it falls back to the defaults of the plugin. It also
    falls back to the defaults if there is no plugin at all: a backend whose
    dynamic plugin is not imported simply keeps the default location reserved,
    for the day when the plugin is imported.
    """
    name: Any = _UNSET_SECTION
    path: Any = _UNSET_SECTION
    if plugin is not None:
        plugin_class = type(plugin)
        for klass in inspect.getmro(context.settings_class):
            # only classes built by the settings metaclass carry plugin state
            bound: Optional[SettingsContext] = vars(klass).get(SETTINGS_CONTEXT_ATTR)
            if bound is None:
                continue
            try:
                klass_plugin = bound.get_plugin(plugin_class)
            except KeyError:
                continue
            if name is _UNSET_SECTION:
                # (the raw parameter readers are the contract with the dynamic plugin)
                # noinspection PyProtectedMember
                name = klass_plugin._raw_dynamic_section_name()
            if path is _UNSET_SECTION:
                # noinspection PyProtectedMember
                path = klass_plugin._raw_dynamic_section_path()
            if name is not _UNSET_SECTION and path is not _UNSET_SECTION:
                break
    if name is _UNSET_SECTION:
        name = DocumentDynamicSettingsPlugin.DEFAULT_SECTION
    if name is None:
        return None  # the flat layout: no section, full names are the keys
    if path is _UNSET_SECTION or path is None:
        return [name]
    return pointer_steps(path) + [name]


class _DynamicPlacement(NamedTuple):
    """Where one dynamic entry sits in the document."""

    section: Optional[List[str]]
    """The section segments; ``None`` in the flat layout."""

    class_key: str
    """The settings class's group key inside the section (empty when flat)."""

    plain_name: str
    """The entry's own name: the leaf key (the full name when flat)."""


def dynamic_entry_placement(
    context: SettingsContext,
    plugin: Optional[DocumentDynamicSettingsPlugin],
    serializer: ISettingsSerializer,
    setting_name: str,
    pattern: str,
    path: Path,
) -> _DynamicPlacement:
    """Return the location of one dynamic entry: the section, the class key, and
    the name.

    The function raises user-facing placement errors in two cases:

    - A name pattern without a class part cannot group the entries by their
      class: the section layout would have nothing to group by and to parse back
      by.
    - A name that was built by a different pattern than the active one does not
      carry the prefix of this class. Slicing past it silently would store the
      entry under a wrong key.

    Both errors name the settings class and the file.
    """
    section = dynamic_section_segments(context, plugin)
    if section is None:
        # the flat layout: the full name is the key
        return _DynamicPlacement(None, "", setting_name)
    prefix = get_dynamic_settings_class_prefix(context.settings_class, serializer, pattern)
    if not prefix:
        # without a class part, entries of different classes would share
        # one object and parsing the section back would be ambiguous
        raise UserFacingError(
            ValueError(
                f"Cannot place dynamic settings of {context.settings_class.__name__} in "
                f"{path}: the name pattern provides no class "
                "part to group them by; use dynamic_settings_section_name = None for "
                "the flat layout"
            )
        )
    plain_name = get_dynamic_setting_name(setting_name, context.settings_class, serializer, pattern)
    if plain_name is None:
        raise UserFacingError(
            ValueError(
                f"Cannot locate dynamic setting {setting_name!r} in "
                f"{path}: the name does not carry this class's prefix"
            )
        )
    delimiter = get_setting_name_delimiter(serializer, context.settings_class)
    return _DynamicPlacement(section, prefix[: -len(delimiter)], plain_name)


def _container_at(node: Any, segments: Sequence[str]) -> Any:
    """Return the node that the segments step into, or ``None`` where the path
    breaks off.

    A segment that consists only of digits reads an array position if the node
    it steps into is a list, and an object key otherwise. The path breaks off at
    a missing key, an out-of-range position, or a scalar in the middle of the
    path.
    """
    for segment in segments:
        index = array_index(segment)
        if isinstance(node, list):
            if index is None or index >= len(node):
                return None
            node = node[index]
        elif isinstance(node, dict):
            node = node.get(segment)
        else:
            return None
        if node is None:
            return None
    return node


def dynamic_settings_names(
    document: Mapping[str, Any],
    *,
    settings_class: type,
    serializer: ISettingsSerializer,
    pattern: str,
    section: Optional[List[str]],
    class_key: str,
    class_location: Sequence[str],
    path: Path,
) -> List[str]:
    """Return the full names of the dynamic entries of the settings class in the
    document.

    The section layout holds one nested object per settings class. The caller
    passes in the location of the group of the class inside the section, in the
    own spelling of its format (a single dotted key for JSON, nested table
    levels for TOML). A flat layout picks the full names of the class out of the
    document root. The names are returned sorted.

    A section or a class group that is missing from the document holds no
    entries. One that holds a non-object is a broken document, and it raises the
    user-facing error that names the location and the file.
    """
    if section is None:
        # flat layout: full names are the top-level keys; the split tells
        # this class's dynamic names from everything else in the document
        return sorted(
            name
            for name in document
            if get_dynamic_setting_name(name, settings_class, serializer, pattern) is not None
        )
    node: Any = _container_at(document, section[:-1])
    if not isinstance(node, dict):
        return []  # the section location does not exist in this document
    node = node.get(section[-1])
    if node is None:
        return []
    if not isinstance(node, dict):
        raise UserFacingError(
            ValueError(
                f"Dynamic settings section {pointer_display(section)!r} in "
                f"{path} must hold an object, got a {type(node).__name__}"
            )
        )
    entries: Any = _container_at(node, class_location[:-1])
    if not isinstance(entries, dict):
        return []  # the class location does not exist in this document
    entries = entries.get(class_location[-1])
    if entries is None:
        return []  # this class keeps no entries in the section
    if not isinstance(entries, dict):
        raise UserFacingError(
            ValueError(
                f"Dynamic settings of {class_key!r} in {path} "
                f"must hold an object, got a {type(entries).__name__}"
            )
        )
    return sorted(
        get_dynamic_setting_full_name(name, settings_class, serializer, pattern) for name in entries
    )


def dynamic_writer_group(context: SettingsContext, group_metadata: str) -> Optional[str]:
    """Return the group key of the writing class that a reading class declared;
    ``None`` if none is declared.

    The key is the textual address of the entries of the writer in the document:
    the class part of the names of the writer, after the pattern is expanded.
    The reading side spells it, because it knows the writer by contract, not by
    import. A class without the binding reads no dynamic entries.
    """
    key: Any = context.get_class_metadata(group_metadata)
    return key if isinstance(key, str) and key else None


def dynamic_flat_prefix(serializer: ISettingsSerializer, class_key: str) -> str:
    """Return the spelling of the names of one group in the flat layout: the ``D``
    marker and the group key, with a delimiter around each of them.
    """
    delimiter = get_setting_name_delimiter(serializer, None)
    return DYNAMIC_SETTING_NAME_PREFIX + delimiter + class_key + delimiter


def dynamic_reader_entry_segments(
    context: SettingsContext,
    plugin: Optional[DocumentDynamicSettingsPlugin],
    serializer: ISettingsSerializer,
    setting_name: str,
    class_key: str,
    class_location: Sequence[str],
    path: Path,
) -> List[str]:
    """Return the location segments of one entry of a group that is being read,
    which is the group of the writer.

    The reading class declares the group key of the writer, so the storage name
    of the entry is parsed against that key, not against the own names of the
    reading class. A name that does not carry the prefix of the group would end
    up under a wrong key, and the user-facing error says so. The flat layout
    keeps the full name as the root key, unchanged.
    """
    section = dynamic_section_segments(context, plugin)
    if section is None:
        return [setting_name]
    prefix = dynamic_flat_prefix(serializer, class_key)
    if not setting_name.startswith(prefix):
        raise UserFacingError(
            ValueError(
                f"Cannot locate dynamic setting {setting_name!r} in "
                f"{path}: the name does not carry the writer group's prefix"
            )
        )
    return [*section, *class_location, setting_name[len(prefix) :]]


def dynamic_reader_names(
    document: Mapping[str, Any],
    *,
    serializer: ISettingsSerializer,
    class_key: str,
    section: Optional[List[str]],
    class_location: Sequence[str],
    path: Path,
) -> List[str]:
    """Return the full names of the entries of the writer's group in the document.

    This is the reading counterpart of :func:`dynamic_settings_names`. The
    section layout reads the own object of the group. The caller passes in its
    location in the spelling of the format (a single key for JSON, nested table
    levels for TOML). A flat layout picks the ``D``-prefixed names of the group
    out of the document root. The names are returned sorted. A section or a
    group that is missing from the document holds no entries, while one that
    holds a non-object is a broken document and raises an error.
    """
    prefix = dynamic_flat_prefix(serializer, class_key)
    if section is None:
        return sorted(name for name in document if name.startswith(prefix))
    node: Any = _container_at(document, section[:-1])
    if not isinstance(node, dict):
        return []  # the section location does not exist in this document
    node = node.get(section[-1])
    if node is None:
        return []
    if not isinstance(node, dict):
        raise UserFacingError(
            ValueError(
                f"Dynamic settings section {pointer_display(section)!r} in "
                f"{path} must hold an object, got a {type(node).__name__}"
            )
        )
    entries: Any = _container_at(node, class_location[:-1])
    if not isinstance(entries, dict):
        return []  # the group location does not exist in this document
    entries = entries.get(class_location[-1])
    if entries is None:
        return []  # the group keeps no entries in this document
    if not isinstance(entries, dict):
        raise UserFacingError(
            ValueError(
                f"Dynamic settings of {class_key!r} in {path} "
                f"must hold an object, got a {type(entries).__name__}"
            )
        )
    return sorted(prefix + name for name in entries)
