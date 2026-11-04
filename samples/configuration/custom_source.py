"""
Example: the plugin-author API of Advexp.Configuration. It shows a source of
your own, built on the public contracts.

One file builds a complete source:

- an attribute (the class that the member factory builds, with the own
  parameters of the source);
- a serializer (how values are read);
- a plugin object (the registration pair);
- the builder of the chain link (what the application passes to
  ``options=``).

All of this is built on what ``advexp.configuration.plugin_api`` exports. The
application-side API of the package is shown in
``samples/configuration/configuration_api.py``.

Run from the repository root with the package installed
(``pip install advexp-configuration``):

    python samples/configuration/custom_source.py
"""

import logging
from typing import Any, Callable, Mapping, Optional, Sequence

import advexp.configuration as adv_config
import advexp.configuration.plugin_api as api

# ---------------------------------------------------------------------------
# The source: a registry of sections, external to the serializer — the way
# a configuration file or os.environ sits outside a real one
# ---------------------------------------------------------------------------

REGISTRY: dict = {"limits": {"timeout": "30", "depth": "8"}}


class RegistrySetting(api.ConfigurationAttribute):
    """Source attribute: the value of the member lives in a registry section.

    ``section=`` is the own parameter of the source, and its serializer reads it.
    The other parameters are the shared contract of the family (name, default,
    and the constraint parameters), and they are passed to the base class
    unchanged.
    """

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        default: Any = adv_config.REQUIRED,
        section: str,
        metadata: Optional[Mapping[str, Any]] = None,
        aliases: Optional[Sequence[str]] = None,
        gt: Any = None,
        ge: Any = None,
        lt: Any = None,
        le: Any = None,
        eq: Any = None,
        ne: Any = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        regex: Optional[str] = None,
        validator: Optional[Callable[[Any], bool]] = None,
        when: Any = None,
    ) -> None:
        super().__init__(
            name=name,
            default=default,
            metadata=metadata,
            aliases=aliases,
            gt=gt,
            ge=ge,
            lt=lt,
            le=le,
            eq=eq,
            ne=ne,
            min_length=min_length,
            max_length=max_length,
            regex=regex,
            validator=validator,
            when=when,
        )
        # the parameter lives on the attribute: the serializer reads it through
        # attribute_of, the family's way of seeing the writer's intent
        self.section: str = section


def registry_setting(
    *,
    name: Optional[str] = None,
    default: Any = adv_config.REQUIRED,
    section: str,
    metadata: Optional[Mapping[str, Any]] = None,
    aliases: Optional[Sequence[str]] = None,
    gt: Any = None,
    ge: Any = None,
    lt: Any = None,
    le: Any = None,
    eq: Any = None,
    ne: Any = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    regex: Optional[str] = None,
    validator: Optional[Callable[[Any], bool]] = None,
    when: Any = None,
) -> Any:
    """Declare a member on this source. This is the type-checker-friendly spelling
    of ``RegistrySetting``.

    It is a thin counterpart of the attribute class (same parameters, same
    attribute), and it is the piece that a custom source needs for static
    typing. Assigning the attribute instance to an annotated member is valid
    Python, but type checkers cannot see that the metaclass replaces it with a
    value descriptor, so they report a type mismatch. They accept a plain
    function that returns ``Any``.
    """
    return RegistrySetting(
        name=name,
        default=default,
        section=section,
        metadata=metadata,
        aliases=aliases,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        eq=eq,
        ne=ne,
        min_length=min_length,
        max_length=max_length,
        regex=regex,
        validator=validator,
        when=when,
    )


class RegistrySerializer(api.SettingsBaseSerializer):
    """Registry source: a section's keys, addressed as ``section.name``."""

    # -- ISettingsSerializer ---------------------------------------------------

    def load(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> Any:
        # the serializer sees the parameter through the registered attribute:
        # attribute_of answers the instance the member was declared with.
        # The declared aliases widen the read — the delivered name first,
        # then each alias, the first key found wins — through the shared
        # helper plugin_api ships for this loop
        source = self.attribute_of(attr, RegistrySetting)
        section = REGISTRY.get(source.section, {}) if source is not None else {}
        for key in api.setting_name_candidates(setting_name, attr):
            if key in section:
                return section[key]
        return api.NOT_FOUND

    def save(
        self,
        setting_name: str,
        attr: Optional[api.ISettingAttribute],
        value: Any,
    ) -> None:
        """Refused with an error: a read-only source never writes. The contract
        requires the method, but the package never calls it, so a caller that reaches
        it has mistaken the source for a storage backend.
        """
        raise api.UserFacingError(
            NotImplementedError("the registry source is read-only: it loads and never writes")
        )

    def delete(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> None:
        """Refused with an error: a read-only source never deletes."""
        raise api.UserFacingError(
            NotImplementedError("the registry source is read-only: it loads and never deletes")
        )

    def contains(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> bool:
        source = self.attribute_of(attr, RegistrySetting)
        if source is None:
            return False
        section = REGISTRY.get(source.section, {})
        return any(key in section for key in api.setting_name_candidates(setting_name, attr))

    # -- ISettingNameDescriber ---------------------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[api.ISettingAttribute]
    ) -> str:
        # the source's own spelling of the address, for load diagnostics:
        # the reader learns where to provide the value
        source = self.attribute_of(attr, RegistrySetting)
        if source is None:
            return f"registry key '{setting_name}'"
        return f"registry section '{source.section}', key '{setting_name}'"


class RegistryPlugin(api.SettingsBasePlugin):
    """Plugin object; the base's declarative binding registers the pair."""

    binding = api.AttributeSerializerBinding(RegistrySetting, RegistrySerializer)

    @property
    def plugin_name(self) -> str:
        return "Registry"


adv_config.LibraryConfiguration.register_settings_plugin(RegistryPlugin)


def registry_source() -> api.SourceBinding:
    """Declare a registry link: the chain spelling of this source.

    A source joins a layered class as a link. The builder wraps a
    :class:`~advexp.configuration.plugin_api.SourceLink` of the family in a
    :class:`~advexp.configuration.plugin_api.SourceBinding`, which is the object
    that the application passes directly to ``Sources(...)`` or ``options=``.

    The link here carries no parameters of its own (the sections live on the
    members). A source that carries a file would put its file, subtree, and
    naming into the params of the link, and it would read them in its serializer
    through ``ISourceLinkSink``.
    """
    return api.SourceBinding(api.SourceLink(attribute_class=RegistrySetting))


# ---------------------------------------------------------------------------
# A configuration class served by the source, and the walkthrough
# ---------------------------------------------------------------------------


class EngineConfig(
    adv_config.Configuration,
    options=registry_source(),
):
    """The demo class served by the source built in this file."""

    # explicit keys keep the demo readable; the section is the source's
    # own parameter, the key is the family's shared naming (the full pattern
    # name without name=)
    timeout: int = registry_setting(name="timeout", section="limits", ge=1, le=60)
    depth: int = registry_setting(name="depth", section="limits", default=4)
    label: str = registry_setting(name="label", section="labels", default="primary")
    # aliases: the registry may still carry the pre-rename key; the source
    # honors them through the same shared helper as the bundled ones
    workers: int = registry_setting(
        name="workers", section="limits", aliases=["threads"], default=1
    )


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="log: %(message)s")
    adv_config.LibraryConfiguration.set_log_level(logging.INFO)

    section("the source through the load pass")
    # 'limits' holds timeout="30" and depth="8": both convert and pass
    EngineConfig.load_configuration()
    print(f"timeout = {EngineConfig.timeout!r} ('30' from the registry, converted)")
    print(f"depth   = {EngineConfig.depth!r}")
    print(f"label   = {EngineConfig.label!r} (the section is empty, so the default is used)")

    section("the parameter reaching the serializer: same key, another section")
    REGISTRY["labels"] = {"label": "secondary"}
    EngineConfig.load_configuration()
    print(f"label   = {EngineConfig.label!r} (the 'label' key inside the 'labels' section)")

    section("aliases: the registry's old key keeps serving the member")
    # only the pre-rename key is in the section: the alias serves the member
    REGISTRY["limits"]["threads"] = "8"
    EngineConfig.load_configuration()
    print(f"workers = {EngineConfig.workers!r} (read from the alias key 'threads')")
    # the primary key outranks the alias once the section carries it
    REGISTRY["limits"]["workers"] = "2"
    EngineConfig.load_configuration()
    print(f"workers = {EngineConfig.workers!r} (the primary key 'workers' takes precedence)")

    section("diagnostics quote the source's own address")
    del REGISTRY["limits"]["timeout"]
    try:
        EngineConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"{type(entry).__name__}: {entry}")
    # the message names the section and the key: exactly where to provide
    # the value — that is what ISettingNameDescriber is for


if __name__ == "__main__":
    main()
