# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Public API for settings backend (plugin) authors.

The library serves two audiences through two import sites: applications
import :mod:`advexp.settings` (``Settings``, ...), and backend authors
import this module. This module exports the following, grouped by role:

- base classes to derive from: :class:`SettingsAttribute` (the setting
  attribute base of this package: the family base plus the defaults of this
  package, where an omitted ``default=`` means ``NO_DEFAULT`` and ``None``
  stands in), :class:`SettingsBaseSerializer` (a storage backend with no-op
  defaults, plus the value-form helpers
  :meth:`~SettingsBaseSerializer.to_json_value` and
  :meth:`~SettingsBaseSerializer.to_storage_string`),
  :class:`SettingsBasePlugin` (context binding on top of the plugin
  contract, plus the declarative binding: a declared
  :class:`AttributeSerializerBinding` is registered by its ``setup()``),
  :class:`DynamicSettingsBasePlugin` (the collection of runtime-named
  settings, pinned to a static backend through its mandatory binding, for
  which :class:`DynamicSettingAttribute` is the namespaced form of the pin),
  and :class:`DocumentDynamicSettingsPlugin` (the document-backend layer
  over it, which carries the two parameters that place the section of the
  dynamic entries);
- the contracts that signatures use: :class:`ISettingAttribute` (what a
  setting attribute is, and what the metaclass detects),
  :class:`ISettingsPlugin` (the plugin contract that ``get_plugin``
  accepts), :class:`ISettingsSerializer` (the mandatory serializer
  contract), :class:`ISettingsSerializerWishes`,
  :class:`ISerializerNotificationSink`, :class:`ISettingNameDescriber` and
  :class:`ISourceDescriber` (optional capabilities), and
  :class:`IDynamicSettingsInfo` (the optional storage enumeration for
  dynamic-settings plugins);
- the declarative binding: :class:`AttributeSerializerBinding`;
- the source seat of a custom backend: :class:`SourceLink` (the link that a
  ``*_source`` builder of this package stores under the metadata key of the
  family; it is the plain-data form of a storage binding) and
  :func:`register_source_link_key` (the registration of the seat; the
  import of a backend module is the natural place for it). For a file
  backend whose binding spells a templated path, there are
  :class:`EnvParameter` and :func:`env_parameter`. For a backend that ships
  a file seat of its own, there is :func:`register_file_seat`; the
  ``class`` statement then rejects that seat next to the source binding of
  this family;
- the module declarations of the holder of a custom backend:
  :class:`ModuleDefaultMeta` (the metaclass of the holder: assigning a
  ``for_this_module(...)`` marker, which is a tool of the package root, to a
  registered parameter makes the value the value of the declaring module),
  :func:`register_module_default` (opens the parameter, which is spelled as
  one attribute read of the holder, ``lambda holder: holder.<parameter>``; a
  renamed attribute makes the registration fail loudly; it also names the
  validator that every declared value passes) and
  :func:`module_default_for` (the lookup of the backend, with the same
  lambda: it returns the value that the module of the settings class
  declared);
- registration and context: :class:`LibraryConfiguration`,
  :class:`SettingsContext`, and :data:`SETTINGS_CONTEXT_ATTR` (the
  attribute under which each settings class stores its own context, which
  is how a backend reaches the context of any class in the chain);
- sentinels and the error: :data:`NO_DEFAULT`, :data:`NOT_FOUND`, and
  :class:`UserFacingError`;
- the dynamic name helpers: :func:`get_dynamic_settings_class_prefix` (the
  class part of the storage names, for backends that lay out the entries).
  The full name of one entry and the plain name behind it are given by the
  context pair :meth:`SettingsContext.get_dynamic_setting_full_name` and
  :meth:`SettingsContext.get_dynamic_setting_name`;
- the alias helpers: :func:`setting_name_candidates` (the addresses that a
  load tries: the delivered name, then the declared ``aliases=`` of the
  member; the first address found wins) and :func:`spelled_with_aliases` (an
  address phrase with the aliases listed next to it, used in the load
  diagnostics that a backend spells through ``ISettingNameDescriber``).

Python does not enforce visibility, so this boundary is an explicit module
rather than a language rule.

Everything that a backend needs is re-exported here.
``advexp.settings._internal`` is private and may be refactored at any time;
importing it from plugin or application code is not supported (this is
enforced by the ruff ``TID251`` ban and a repository test).

A minimal backend consists of: a setting attribute derived from
:class:`SettingsAttribute`; a serializer that implements
:class:`ISettingsSerializer` (or derives from
:class:`SettingsBaseSerializer`, to start from the no-op defaults); a
:class:`SettingsBasePlugin` subclass that declares an
:class:`AttributeSerializerBinding` (the base ``setup()`` registers it); and
a ``LibraryConfiguration.register_settings_plugin(...)`` call at module
import time. Importing the plugin module is what enables the plugin.
``samples/settings/custom_backend.py`` builds such a backend in a single
file.

Three names are shared with the top level, because both audiences need
them: ``NO_DEFAULT`` and ``REQUIRED`` (custom attributes and serializers
read these default markers: no default given, and a required member) and
``LibraryConfiguration`` (plugin registration lives next to its
application-level parameters).
"""

# (the facade's one sanctioned import of the internals; the ruff TID251 ban
# keeps everyone else out of _internal)
# noinspection PyProtectedMember
from advexp.settings._internal.facade_sources import (
    NO_DEFAULT,
    NOT_FOUND,
    PACKAGE_NAME,
    REQUIRED,
    SETTINGS_CONTEXT_ATTR,
    AttributeSerializerBinding,
    DocumentDynamicSettingsPlugin,
    DynamicSettingAttribute,
    DynamicSettingsBasePlugin,
    EnvParameter,
    IDynamicSettingsInfo,
    ISerializerNotificationSink,
    ISettingAttribute,
    ISettingNameDescriber,
    ISettingsPlugin,
    ISettingsSerializer,
    ISettingsSerializerWishes,
    ISourceDescriber,
    LibraryConfiguration,
    ModuleDefaultMeta,
    SettingRef,
    SettingsAttribute,
    SettingsBasePlugin,
    SettingsBaseSerializer,
    SettingsContext,
    SourceLink,
    UserFacingError,
    env_parameter,
    family_entry_key,
    get_dynamic_settings_class_prefix,
    module_default_for,
    register_file_seat,
    register_module_default,
    register_source_link_key,
    setting_name_candidates,
    spelled_with_aliases,
)

__all__ = [
    "UserFacingError",
    "AttributeSerializerBinding",
    "EnvParameter",
    "SettingsBaseSerializer",
    "DynamicSettingsBasePlugin",
    "DocumentDynamicSettingsPlugin",
    "DynamicSettingAttribute",
    "IDynamicSettingsInfo",
    "ISettingsSerializer",
    "ISettingsSerializerWishes",
    "ISerializerNotificationSink",
    "ISettingNameDescriber",
    "ISourceDescriber",
    "SourceLink",
    "env_parameter",
    "get_dynamic_settings_class_prefix",
    "register_file_seat",
    "register_source_link_key",
    "ModuleDefaultMeta",
    "module_default_for",
    "register_module_default",
    "setting_name_candidates",
    "spelled_with_aliases",
    "NO_DEFAULT",
    "NOT_FOUND",
    "PACKAGE_NAME",
    "REQUIRED",
    "ISettingAttribute",
    "SettingsAttribute",
    "SettingRef",
    "ISettingsPlugin",
    "SettingsBasePlugin",
    "LibraryConfiguration",
    "SettingsContext",
    "SETTINGS_CONTEXT_ATTR",
    "family_entry_key",
]
