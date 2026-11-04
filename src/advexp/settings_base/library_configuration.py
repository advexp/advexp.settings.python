# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Global configuration and plugin registries.

Holds the attribute-to-serializer registry, the plugin registry, the
class-metadata validators and logging setup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Type, cast

from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.settings_plugin_interface import ISettingsPlugin
from advexp.settings_base.settings_serializer_interface import ISettingsSerializer

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    # SettingsBasePlugin imports this module for the declarative binding
    from advexp.settings_base.settings_base_plugin import PluginT

SerializerFactory = Type[ISettingsSerializer]
"""The serializer class the registry holds; calling it builds the instance
(the per-pass :class:`~advexp.settings_base.serializer_cache.SerializerCache`
does the calling, injecting the pass's context through the wishes contract)."""

ClassMetadataValidator = Callable[[Any], Optional[str]]
"""A validator of one class metadata key: returns the problem with the
stored value as a human-readable sentence, or ``None`` when the value is
valid. The machinery turns a problem into the error naming the settings
class and the metadata key; a validator never raises on its own."""

FAMILY_ENTRY_SEPARATOR = "."
"""Joins a family key with the declaring class's module and name in the
per-class entry key."""


def family_entry_key(family_key: str, declaring_class: type) -> str:
    """Return the metadata key of the own entry of one class in the options of a
    family.

    The options of a family are stored per declaring class, so a subclass with
    its own options coexists with the base class instead of replacing it. The
    key is the family key joined with the module and the name of the class. The
    module keeps classes with the same name from different modules distinct. User
    code never spells this string: the metadata channel names the class itself,
    and the machinery builds the key.
    """
    module = declaring_class.__module__
    return (
        f"{family_key}{FAMILY_ENTRY_SEPARATOR}{module}"
        f"{FAMILY_ENTRY_SEPARATOR}{declaring_class.__name__}"
    )


BASE_LOGGER_NAME = "advexp.settings_base"
"""Channel of the base's own context-free diagnostics."""

FAMILY_LOGGER_NAME = "advexp"
"""The family's logging root: every channel of the family lives under it,
so one level set here governs them all."""

LOGGER_NAME_ATTR = "__logger_name__"
"""Class attribute a distribution's root settings class declares to route
the machinery's records onto its own channel. Inherited by every subclass:
all classes of a distribution share a single channel. The name is the
family's own vocabulary: every distribution of the family — settings,
configuration, plugins — declares it the same way."""

ATTRIBUTE_BASE_ATTR = "__attribute_base__"
"""Class attribute a distribution's root settings class declares to name
the attribute base of its members: every member the class's body declares
through that base belongs to the distribution, and the ``class`` statement
refuses a member declared with another distribution's attribute. Inherited
by every subclass; the boundary reads it in
:mod:`advexp.settings_base.family_boundaries`."""

MEMBER_TERM_ATTR = "__member_term__"
"""Class attribute a distribution's root settings class declares to name
the word its diagnostics call the members by — one vocabulary per
distribution, so a record on the package's channel never speaks another
package's word. Inherited by every subclass and read by
:func:`member_term`, which words the machinery's messages with it."""


def member_term(settings_class: Optional[type]) -> str:
    """Return the word by which the distribution of the settings class calls its
    members.

    There is one vocabulary per distribution. The root settings class declares
    it next to its other declarations, and every subclass inherits it. The
    messages of the machinery use it: load records, abort entries, and the error
    of a read of a required member say ``member 'host' ... of 'AppConfig'`` or
    ``setting 'host' ... of 'AppSettings'``. A ``None`` argument (a hand-built
    call with no class at hand) gives the word ``setting``, which is used in the
    whole family.
    """
    if settings_class is None:
        return "setting"
    return getattr(settings_class, MEMBER_TERM_ATTR, "setting")


def logger_for(settings_class: Optional[type]) -> logging.Logger:
    """Return the logging channel of the distribution that drives the class.

    There is one logger per distribution, not per settings class: the root class
    of the distribution declares the name of the channel, and every subclass
    inherits it. ``logging.getLogger`` returns the same logger object for the
    same name, so ten settings classes of one distribution all log through one
    logger. Without a declaration (a helper that has no class context), the own
    channel of the base is used.
    """
    name = BASE_LOGGER_NAME
    if settings_class is not None:
        name = getattr(settings_class, LOGGER_NAME_ATTR, name)
    return logging.getLogger(name)


class LibraryConfiguration:
    """Library-wide configuration (all state is class-level).

    The registries of the family live here (attributes to serializers, plugin
    classes, and class-metadata validators), next to the parameter that an
    application touches: the log level of the whole family. The form of storage
    names is not part of it: a name pattern is the own vocabulary of the naming
    backend, and every backend family carries its own.
    """

    _attribute_serializers: Dict[Type[ISettingAttribute], SerializerFactory] = {}
    _plugin_classes: Dict[Type[ISettingsPlugin], Type[ISettingsPlugin]] = {}
    _class_metadata_validators: Dict[str, ClassMetadataValidator] = {}

    # -- logging ---------------------------------------------------------

    @classmethod
    def set_log_level(cls, level: int) -> None:
        """Set the log level on the root of the family, which governs every channel.

        The records of the machinery are carried by the channel of the distribution
        that drives them (``advexp.settings_base``, or the own channel of a
        distribution). All of these channels are under the ``advexp`` root, so one
        level that is set here covers them, whichever distribution is in use. A
        channel that has its own explicitly set level keeps it, because the
        ``logging`` module resolves the nearest level that is set.
        """
        logging.getLogger(FAMILY_LOGGER_NAME).setLevel(level)

    @classmethod
    def logger(cls) -> logging.Logger:
        """Return the logging channel of the family, ready to be configured.

        Every channel of the family (the own channel of a distribution, and the one
        of the foundation) lives under the root of the family. One object therefore
        receives every record that the machinery writes: you can set a level on it
        or add a handler with a formatter to it, all with standard ``logging``. The
        name stays the own spelling of the library: the application configures the
        channel that it was handed, and never one that it looked up by name:

        ```python
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s:%(name)s: %(message)s")
        )
        logger = LibraryConfiguration.logger()
        logger.addHandler(handler)
        logger.propagate = False  # the application's root stays quiet
        ```

        The propagation parameter matters when the application also configures the
        root logger. ``logging.basicConfig()`` puts a handler there, so a channel
        that is configured here would duplicate its records. Turning the propagation
        off prevents this. An application that configures nothing but
        ``basicConfig`` needs none of this: the records flow to its root in the usual
        way.
        """
        return logging.getLogger(FAMILY_LOGGER_NAME)

    # -- registries --------------------------------------------------------

    @classmethod
    def register_settings_attribute(
        cls,
        attribute_class: Type[ISettingAttribute],
        serializer_factory: SerializerFactory,
    ) -> None:
        """Map an attribute class to the serializer class that serves its settings.

        Registering the same pair again is a no-op: several plugins may register one
        shared attribute-to-serializer pair. Registering the same attribute class
        with a *different* serializer class raises :class:`ValueError`: two backends
        that claim one attribute are a conflict, not an override.

        A dynamic-attribute pin is registered in the same way, as a slot of its own:
        the serializer that is bound to it serves only the dynamic entries, and it
        never touches the registration of the attribute class that the pin
        namespaces.
        """
        if not isinstance(attribute_class, type):
            raise TypeError("attribute_class must be a class")
        existing = cls._attribute_serializers.get(attribute_class)
        if existing is not None and existing is not serializer_factory:
            raise ValueError(
                f"'{attribute_class.__name__}' attribute is already registered "
                "with a different serializer class"
            )
        cls._attribute_serializers[attribute_class] = serializer_factory

    @classmethod
    def _get_serializer_factory(
        cls, attribute_class: Type[ISettingAttribute]
    ) -> Optional[SerializerFactory]:
        """Return the serializer class that is registered for the attribute class.

        There is no walk over subclasses: each plugin registers its own concrete
        attribute classes, including a dynamic-attribute pin, which has a slot of its
        own.
        """
        return cls._attribute_serializers.get(attribute_class)

    @classmethod
    def register_settings_plugin(cls, plugin_class: Type[ISettingsPlugin]) -> None:
        """Register a plugin class and call its ``setup()`` hook, if there is one.

        A plugin may define a ``setup()`` class method. It runs once, right at
        registration, and it is the place where a plugin usually registers its
        attribute-to-serializer pairs through :meth:`register_settings_attribute`.
        ``setup()`` is optional: a plugin may register its pieces inline at import
        time instead.

        :class:`~advexp.settings_base.settings_base_plugin.SettingsBasePlugin` ships
        a ``setup()``. It registers the declared
        ``attribute_class``/``serializer_class`` pair, so a plugin that derives from
        it usually declares the pair instead of writing its own ``setup()``. Bundled
        plugins call this method when their module is imported, which is what makes
        importing a plugin module enable the plugin.

        Registering a plugin that is already registered is a no-op: the ``setup()``
        hook does not run a second time, so repeated imports or an explicit
        re-registration leave the state of the plugin untouched.
        """
        if plugin_class in cls._plugin_classes:
            return
        setup: Optional[Callable[[], None]] = getattr(plugin_class, "setup", None)
        if setup is not None:
            # (the checker does not narrow the getattr result past the check)
            # noinspection PyCallingNonCallable
            setup()
        cls._plugin_classes[plugin_class] = plugin_class

    @classmethod
    def _resolve_plugin_class(cls, plugin_class: Type[PluginT]) -> Type[PluginT]:
        """Exact registration wins; otherwise the first registered subclass
        is returned."""
        if plugin_class in cls._plugin_classes:
            # the registry guarantees the stored class is the requested one
            # (the cast is for mypy: it has no membership narrowing for dicts)
            # noinspection PyUnnecessaryCast
            return cast("Type[PluginT]", cls._plugin_classes[plugin_class])
        for registered in cls._plugin_classes:
            if issubclass(registered, plugin_class):
                # (the cast is for mypy: it has no narrowing for dict values)
                # noinspection PyUnnecessaryCast
                return cast("Type[PluginT]", registered)
        raise KeyError(
            f"Plugin {plugin_class.__name__} is not registered. "
            "Import the plugin module to enable the plugin."
        )

    @classmethod
    def registered_plugin_classes(cls) -> List[Type[ISettingsPlugin]]:
        """Return the registered plugin classes, in registration order."""
        return list(cls._plugin_classes)

    # -- class metadata validation -------------------------------------------

    @classmethod
    def register_class_metadata_validator(
        cls, metadata_name: str, validator: ClassMetadataValidator
    ) -> None:
        """Map a class metadata key to the validator of its values.

        A plugin family that owns a metadata key (its options vocabulary) registers
        the validator when its module is imported. This is the same convention that
        the plugin registry follows, where the import enables the plugin.

        The machinery then checks every stored value. A declaration in a class body
        makes the ``class`` statement fail, and a runtime call of
        :meth:`~advexp.settings_base.context.SettingsContext.set_class_metadata`
        raises an error before the value is stored. Keys that have no validator
        belong to the open channel alone: whatever the application stores there is
        never questioned.

        Registering the same pair again is a no-op: a family module that is imported
        twice leaves the state untouched. Registering the same key with a
        *different* validator raises :class:`ValueError`: two families that claim one
        key are a conflict, not an override.
        """
        existing = cls._class_metadata_validators.get(metadata_name)
        if existing is not None and existing is not validator:
            raise ValueError(
                f"the '{metadata_name}' class metadata key is already registered "
                "with a different validator"
            )
        cls._class_metadata_validators[metadata_name] = validator

    @classmethod
    def _is_family_metadata_key(cls, metadata_name: str) -> bool:
        """Return whether the key is the flat spelling of a family: a key that a family
        registered for itself, under its exact name.

        The flat spelling means "the own entry of this class" everywhere. The
        declaration in a ``class`` statement is stored under the per-class key of the
        declaring class, and the runtime channel addresses the own entry of the class
        through the flat key.
        """
        return metadata_name in cls._class_metadata_validators

    @classmethod
    def _family_key_of_entry(cls, metadata_name: str) -> Optional[str]:
        """Return the family key if the name is the per-class entry spelling of a
        registered family; return ``None`` for every other key.

        The per-class spelling is the family key joined with the entry separator. The
        flat spelling and unclaimed keys return ``None``. The machinery uses this
        function to tell the entries of a family from the keys of the open channel.
        A free key that happens to start like an entry of a family was always read as
        an entry of that family, because the validator already treated it in that
        way.
        """
        for family_key in cls._class_metadata_validators:
            if metadata_name.startswith(family_key + FAMILY_ENTRY_SEPARATOR):
                return family_key
        return None

    @classmethod
    def _get_class_metadata_validator(cls, metadata_name: str) -> Optional[ClassMetadataValidator]:
        """Return the validator that is registered for the metadata key, or ``None`` if
        the key has none (an unclaimed key, or a family module that is not imported).

        The per-class entries of a family are resolved through the validator of the
        family: a key that starts with a registered family key and the entry
        separator is validated by the rules of that family.
        """
        exact = cls._class_metadata_validators.get(metadata_name)
        if exact is not None:
            return exact
        family_key = cls._family_key_of_entry(metadata_name)
        if family_key is not None:
            return cls._class_metadata_validators[family_key]
        return None
