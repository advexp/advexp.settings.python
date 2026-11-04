# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Full setting names.

A storage name is either the pattern, expanded with the module (namespace),
the class name, and the member name of the settings class, or the explicit
``attribute.name``.

Dynamic entries add the ``D`` mode prefix, which keeps them apart from static
names in the same storage. There is no service mode: nothing in the library
persists service data per class. When a consumer needs a display order of
dynamic settings, it is declared in code through class metadata, and it is
not stored.

When the serializer implements ``ISettingsSerializerWishes``, name fragments
are sanitized and joined through its "wishes"
(``remove_inappropriate_symbols`` and ``delimiter``). Otherwise, the defaults
are used. A ``delimiter()`` wish other than ``'.'`` and ``'_'`` cannot serve
storage names. It falls back to the default delimiter, with a logged
warning.

The pattern is the own vocabulary of the name builder, not a configuration:
the builders take it as a parameter and default to the full pattern below. A
backend with its own naming passes its own pattern (the JSON family, for
example, resolves the pattern from its family options and from the
parameter of its dynamic side), while a backend that never customizes names
needs no parameter at all.

Names carry no format-version prefix: values are stored in self-describing
formats (JSON/YAML), so a version marker has nothing to protect. If the name
format ever breaks, introducing a prefix and reading legacy unprefixed names
is a localized change in this module.
"""

from __future__ import annotations

import enum
from typing import Optional, Set, Tuple

from advexp.settings_base.library_configuration import logger_for
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer
from advexp.settings_base.settings_serializer_wishes_interface import (
    ISettingsSerializerWishes,
)

DYNAMIC_SETTING_NAME_PREFIX = "D"

NAMESPACE_PATTERN_NAME = "{NamespaceName}"
"""Pattern slot expanding to the settings class's module name."""

CLASS_NAME_PATTERN_NAME = "{ClassName}"
"""Pattern slot expanding to the settings class's own name."""

FIELD_NAME_PATTERN_NAME = "{FieldName}"
"""Pattern slot expanding to the member (field) name. A pattern without it
cannot hold per-setting names: every name it builds would collide."""

DELIMITER_PATTERN_NAME = "{Delimiter}"
"""Pattern slot expanding to the serializer's delimiter wish (``'.'`` or
``'_'``); the storage-facing spelling of the separator between the parts."""

DEFAULT_SETTINGS_NAME_PATTERN = (
    NAMESPACE_PATTERN_NAME
    + DELIMITER_PATTERN_NAME
    + CLASS_NAME_PATTERN_NAME
    + DELIMITER_PATTERN_NAME
    + FIELD_NAME_PATTERN_NAME
)
"""The full default pattern: ``{module}.{class}.{member}``. The class part
keeps the names of two settings classes apart in one storage, and the
namespace part keeps same-named classes of two modules apart."""

_DEFAULT_DELIMITER = "."

_DELIMITER_WISHES = (".", "_")

_warned_delimiter_classes: Set[type] = set()


class SettingNameMode(enum.Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"


def get_setting_name_delimiter(
    serializer: Optional[ISettingsSerializer], settings_class: Optional[type] = None
) -> str:
    delimiter = _DEFAULT_DELIMITER
    if isinstance(serializer, ISettingsSerializerWishes):
        delimiter = serializer.delimiter()
    if delimiter not in _DELIMITER_WISHES:
        serializer_class = type(serializer)
        # the wish is asked for every name on every pass: warn once per
        # serializer class, not once per name
        if serializer_class not in _warned_delimiter_classes:
            _warned_delimiter_classes.add(serializer_class)
            logger_for(settings_class).warning(
                "%s.delimiter() returned %r: expected '.' or '_', using '.'",
                serializer_class.__name__,
                delimiter,
            )
        delimiter = _DEFAULT_DELIMITER
    return delimiter


def _clean(text: str, serializer: Optional[ISettingsSerializer]) -> str:
    if not isinstance(serializer, ISettingsSerializerWishes):
        return text
    return serializer.remove_inappropriate_symbols(text)


def get_full_setting_name(
    member_name: str,
    attribute: Optional[ISettingAttribute],
    settings_class: Optional[type] = None,
    serializer: Optional[ISettingsSerializer] = None,
    mode: SettingNameMode = SettingNameMode.STATIC,
    pattern: str = DEFAULT_SETTINGS_NAME_PATTERN,
) -> str:
    """Build the storage name for a setting.

    If ``attribute.name`` is unset, the ``pattern`` is expanded with the module
    (namespace), the class name, and the member name of the settings class. An
    explicit ``attribute.name`` replaces the whole pattern. Dynamic entries carry
    no attribute instance and pass ``None``: the pattern is always expanded for
    them.
    """
    delimiter = get_setting_name_delimiter(serializer, settings_class)

    explicit_name = attribute.name if attribute is not None else None
    if explicit_name:
        base = _clean(explicit_name, serializer)
    else:
        pattern = pattern.replace(FIELD_NAME_PATTERN_NAME, _clean(member_name, serializer))
        pattern = pattern.replace(DELIMITER_PATTERN_NAME, delimiter)
        module_name = settings_class.__module__ if settings_class is not None else ""
        class_name = settings_class.__name__ if settings_class is not None else ""
        pattern = pattern.replace(NAMESPACE_PATTERN_NAME, _clean(module_name, serializer))
        pattern = pattern.replace(CLASS_NAME_PATTERN_NAME, _clean(class_name, serializer))
        base = pattern

    full_name = base

    if mode is SettingNameMode.DYNAMIC:
        full_name = DYNAMIC_SETTING_NAME_PREFIX + delimiter + full_name

    return full_name


def setting_name_candidates(
    primary_name: str, attribute: Optional[ISettingAttribute]
) -> Tuple[str, ...]:
    """Return the addresses that a load tries for one setting, with the primary
    address first.

    The primary address is the explicit ``name=`` or the pattern-built one,
    whatever the caller resolved. The declared aliases follow, in their order. A
    load walks the list, and the first address found wins, so the primary address
    outranks every alias, and an alias outranks the aliases that are declared
    after it. A dynamic entry carries no attribute instance, so its delivered
    name is its only candidate.
    """
    aliases = attribute.aliases if attribute is not None else ()
    return (primary_name, *aliases)


def spelled_with_aliases(address: str, aliases: Tuple[str, ...]) -> str:
    """Return an address phrase of a message, with the declared aliases listed next
    to it.

    For a member without aliases, the phrase is ``environment variable
    'APP_TTL'`` alone. With aliases, it is ``environment variable 'APP_TTL'
    (aliases: 'APP_TTL_OLD')``. This way, the reader of a miss record sees every
    address that the pass checked, not only the primary one. The phrase keeps
    whatever spelling the caller built, and the aliases are joined in their
    declared order.
    """
    if not aliases:
        return address
    listed = ", ".join(f"'{alias}'" for alias in aliases)
    return f"{address} (aliases: {listed})"


def get_dynamic_settings_class_prefix(
    settings_class: type,
    serializer: Optional[ISettingsSerializer] = None,
    pattern: str = DEFAULT_SETTINGS_NAME_PATTERN,
) -> str:
    """Return the name part with which every dynamic entry of ``settings_class``
    starts.

    The function expands the ``pattern`` up to the ``{FieldName}`` slot with the
    namespace and the class name of the class, so a full dynamic name is this
    prefix followed by the setting name. Dynamic-settings plugins use it to pick
    the entries of their class out of the names that a storage enumerates: the
    pattern-expanded names of two settings classes never share a prefix.

    A name pattern without a ``{FieldName}`` slot cannot hold per-setting names
    at all. This is a configuration error, and it raises here, at the first pass
    that needs the prefix.
    """
    head, separator, _ = pattern.partition(FIELD_NAME_PATTERN_NAME)
    if not separator:
        raise ValueError(
            f"Settings name pattern {pattern!r} has no {FIELD_NAME_PATTERN_NAME} slot: "
            "setting names would collide"
        )
    delimiter = get_setting_name_delimiter(serializer, settings_class)
    head = head.replace(DELIMITER_PATTERN_NAME, delimiter)
    module_name = settings_class.__module__ if settings_class is not None else ""
    class_name = settings_class.__name__ if settings_class is not None else ""
    head = head.replace(NAMESPACE_PATTERN_NAME, _clean(module_name, serializer))
    head = head.replace(CLASS_NAME_PATTERN_NAME, _clean(class_name, serializer))
    return head


def get_dynamic_setting_full_name(
    setting_name: str,
    settings_class: type,
    serializer: Optional[ISettingsSerializer] = None,
    pattern: str = DEFAULT_SETTINGS_NAME_PATTERN,
) -> str:
    """Return the full storage name of one dynamic entry of ``settings_class``.

    This is the counterpart of :func:`get_dynamic_setting_name`. It takes the
    plain name by which the settings know the entry, and it expands it to the
    name that the storage sees: the dynamic marker and the class part of the
    pattern are put in front. The public route for backend authors is
    ``SettingsContext.get_dynamic_setting_full_name``, which supplies the class.
    """
    return get_full_setting_name(
        setting_name,
        None,
        settings_class,
        serializer,
        mode=SettingNameMode.DYNAMIC,
        pattern=pattern,
    )


def get_dynamic_setting_name(
    full_name: str,
    settings_class: type,
    serializer: Optional[ISettingsSerializer] = None,
    pattern: str = DEFAULT_SETTINGS_NAME_PATTERN,
) -> Optional[str]:
    """Return the plain setting name for a dynamic full name of ``settings_class``.

    This is the inverse of :func:`get_dynamic_setting_full_name`. It removes the
    dynamic marker and the class part of the pattern, and it leaves the name by
    which the settings know the entry. The result is ``None`` if the name is not
    a dynamic entry of this settings class: a static name, a dynamic entry of
    another class, or foreign data. The public route for backend authors is
    ``SettingsContext.get_dynamic_setting_name``, which supplies the class.
    """
    prefix = (
        DYNAMIC_SETTING_NAME_PREFIX
        + get_setting_name_delimiter(serializer, settings_class)
        + get_dynamic_settings_class_prefix(settings_class, serializer, pattern)
    )
    if not full_name.startswith(prefix):
        return None
    return full_name[len(prefix) :]
