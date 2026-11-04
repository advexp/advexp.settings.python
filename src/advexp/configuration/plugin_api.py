# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Public API for configuration source (plugin) authors.

The package serves two audiences through two import sites: applications
import :mod:`advexp.configuration` (``Configuration``, ...), and source
authors import this module. This module exports the following, grouped by
role:

- base classes to derive from: :class:`ConfigurationAttribute` (the
  setting attribute base of this package: the family base, plus this
  package's own value of the ``default=`` parameter, :data:`REQUIRED`, so
  the members of a derived source are required unless you opt out),
  :class:`SettingsBaseSerializer` (a source backend with no-op defaults,
  plus the value-form helpers
  :meth:`~SettingsBaseSerializer.to_json_value` and
  :meth:`~SettingsBaseSerializer.to_storage_string`),
  :class:`SettingsBasePlugin` (context binding on top of the plugin
  contract, plus the declarative binding: a declared
  :class:`AttributeSerializerBinding` is registered by its
  ``setup()``);
- the read-only dynamic collections, which are the reading side of the
  entries that a writing class of the settings distribution stored:
  :class:`ReadOnlyDocumentDynamicSettingsPlugin` (the reading facade that
  the bundled dynamic plugins derive from: it loads and answers, and
  refuses writes), :class:`DocumentDynamicSettingsPlugin` (the
  document-backend layer under it, which carries the two parameters that
  place the section of the entries), :class:`DynamicSettingsBasePlugin`
  (the root base of the collection), :class:`DynamicSettingAttribute` (the
  namespaced pin that the binding of a dynamic plugin declares) and
  :class:`IDynamicSettingsInfo` (the optional storage enumeration that a
  dynamic source implements);
- the contracts that signatures use: :class:`ISettingAttribute` (what a
  setting attribute is, and what the metaclass detects),
  :class:`ISettingsPlugin` (the plugin contract that ``get_plugin``
  accepts), :class:`ISettingsSerializer` (the mandatory serializer
  contract), :class:`ISettingsSerializerWishes`,
  :class:`ISerializerNotificationSink`, :class:`ISettingNameDescriber` and
  :class:`ISourceDescriber` (optional capabilities), and
  :class:`ISourceLinkSink` (the interface through which a serializer that
  serves as a chain link receives its link);
- the declarative binding: :class:`AttributeSerializerBinding`;
- the chain vocabulary: :class:`SourceLink` (one link of a class's source
  chain), :class:`SourceBinding` (the result of a source builder),
  :class:`Sources` (the chain itself) and :data:`SOURCE_CHAIN_METADATA`
  (the class metadata key under which the chain is stored). These are the
  pieces that the builder of a custom source assembles. This group also
  contains the path parameters of a templated link: :func:`env_parameter`
  with :class:`EnvParameter` (the declaration that the ``parameters=`` of a
  link takes), :data:`LINK_PARAMETERS_PARAM` (the link parameter that
  carries them) and :func:`resolve_templated_path` (the per-pass expansion
  that a file-based source runs over the file of its link);
- registration and context: :class:`LibraryConfiguration`,
  :class:`SettingsContext`, and :data:`SETTINGS_CONTEXT_ATTR` (the
  attribute under which each configuration class stores its own context,
  which lets a source reach the context of any class in the chain);
- sentinels and the error: :data:`NO_DEFAULT`, :data:`REQUIRED` (the
  default of a required member), :data:`NOT_FOUND`, and
  :class:`UserFacingError`;
- the alias helpers: :func:`setting_name_candidates` (the addresses that a
  load tries: the delivered name, then the member's declared ``aliases=``;
  the first address found wins) and :func:`spelled_with_aliases` (an
  address phrase with the aliases listed next to it, used in the load
  diagnostics that a source spells through ``ISettingNameDescriber``).

Python does not enforce visibility, so this boundary is drawn by an
explicit module rather than by a language rule.

Everything that a source needs is re-exported here. The machinery behind it
ships in the ``advexp-settings-base`` distribution, on which this package
depends. ``advexp.configuration._internal`` is private and may be
refactored at any time; importing it from plugin or application code is
not supported (this is enforced by the ruff ``TID251`` ban and a
repository test). A configuration source is a storage backend that only
ever responds to ``load`` (and to ``contains``, where the source can tell).
The serializer contract also requires the write operations, so a read-only
source refuses them with an error: a ``UserFacingError`` around a
``NotImplementedError`` that names the source.

A source joins a class's chain as a link. It consists of: a setting
attribute derived from :class:`ConfigurationAttribute`; a serializer
derived from :class:`SettingsBaseSerializer` (it overrides ``load``, and
``contains`` when the source can tell, and it implements
``ISourceLinkSink`` to read the link's own parameters); a
:class:`SettingsBasePlugin` subclass that declares an
:class:`AttributeSerializerBinding` (the base ``setup()`` registers it); a
``LibraryConfiguration.register_settings_plugin(...)`` call at module
import time; and a builder that returns a :class:`SourceBinding` around a
:class:`SourceLink` of the family. Importing the plugin module is what
enables the plugin, and the builder is what the application passes to
``Sources(...)`` or ``options=``. The ``options`` modules of the bundled
sources (``json_source``, ``env_source`` and the rest) are working
examples.
"""

# (the facade's one sanctioned import of the internals; the ruff TID251 ban
# keeps everyone else out of _internal)
# noinspection PyProtectedMember
from advexp.configuration._internal.facade_sources import (
    LINK_PARAMETERS_PARAM,
    NO_DEFAULT,
    NOT_FOUND,
    PACKAGE_NAME,
    REQUIRED,
    SETTINGS_CONTEXT_ATTR,
    SOURCE_CHAIN_METADATA,
    AttributeSerializerBinding,
    ConfigurationAttribute,
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
    ISourceLinkSink,
    LibraryConfiguration,
    ReadOnlyDocumentDynamicSettingsPlugin,
    SettingsBasePlugin,
    SettingsBaseSerializer,
    SettingsContext,
    SourceBinding,
    SourceLink,
    Sources,
    UserFacingError,
    env_parameter,
    family_entry_key,
    resolve_templated_path,
    setting_name_candidates,
    spelled_with_aliases,
)

__all__ = [
    "UserFacingError",
    "AttributeSerializerBinding",
    "EnvParameter",
    "SettingsBaseSerializer",
    "DocumentDynamicSettingsPlugin",
    "DynamicSettingAttribute",
    "DynamicSettingsBasePlugin",
    "IDynamicSettingsInfo",
    "ReadOnlyDocumentDynamicSettingsPlugin",
    "ISettingAttribute",
    "ISettingsSerializer",
    "ISettingsSerializerWishes",
    "ISerializerNotificationSink",
    "ISettingNameDescriber",
    "ISourceDescriber",
    "ISourceLinkSink",
    "LINK_PARAMETERS_PARAM",
    "NO_DEFAULT",
    "NOT_FOUND",
    "PACKAGE_NAME",
    "REQUIRED",
    "SOURCE_CHAIN_METADATA",
    "ConfigurationAttribute",
    "ISettingsPlugin",
    "SettingsBasePlugin",
    "LibraryConfiguration",
    "SettingsContext",
    "SETTINGS_CONTEXT_ATTR",
    "SourceBinding",
    "SourceLink",
    "Sources",
    "env_parameter",
    "family_entry_key",
    "resolve_templated_path",
    "setting_name_candidates",
    "spelled_with_aliases",
]
