# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of the environment variables backend.

The environment variable name is ``name=`` when it is given. This is the
full address in the storage, and the options of the family do not change
it. Otherwise, the name is the member name built with the naming options of
the family (the prefix and the case), which are stored per declaring class
under the ``ENVIRONMENT_METADATA_OPTIONS`` family key. The entry of the
class that declared the member (the nearest class at or above it) governs
the member, so the own options of a subclass never change the variables of
inherited members.

Declared ``aliases=`` widen the read. Every alias is a full address, like
``name=``. A load looks up the primary name first, then the aliases in
their order, and the first name found wins. This is how a rename is
migrated: an old variable name keeps serving the member. Saving writes only
the primary name. Deleting also drops the alias variables, so a deleted
member cannot come back through an old name.

A member annotated with a dataclass is a nested object. If the
``nested_delimiter`` option of the family is set, the fields of the object
are addressed through the delimiter in every operation: loading merges the
variables onto the declared default (a partial update), saving stores each
field in its own variable, and deleting drops the whole subtree. Nested
addressing is resolved from the primary name only; aliases take no part in
it. The addressing rules are part of the shared vocabulary of the family in
``advexp.settings_base.environment_nested``.

Under ``name_case=NameCase.ANY``, the lookup accepts any spelling of a
built name. The exact spelling wins. If two spellings differ only in case
and none of them matches exactly, the pass fails
(``advexp.settings_base.environment_lookup``).

Only the process environment is supported: the standard library of Python
has no API for variables at the user or machine level.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional, Tuple

from advexp.settings.plugin_api import (
    NOT_FOUND,
    ISettingAttribute,
    SettingsBaseSerializer,
)
from advexp.settings_base.environment_lookup import environment_key
from advexp.settings_base.environment_nested import (
    contains_nested_environment_value,
    delete_nested_environment_values,
    load_nested_environment_value,
    nested_delimiter_of,
    nested_member,
    nested_object_type,
    save_nested_environment_values,
)
from advexp.settings_base.environment_options import (
    ENVIRONMENT_METADATA_OPTIONS,
    build_environment_name,
)
from advexp.settings_base.names import setting_name_candidates, spelled_with_aliases
from advexp.settings_base.setting_member import SettingMember

_PROCESS_ENVIRONMENT = "the process environment"


class EnvironmentVariablesSerializer(SettingsBaseSerializer):
    """Loads and stores settings in the process environment (``os.environ``).

    The environment has no null form, so for this storage ``None`` and a
    missing value are the same: saving ``None`` unsets the variable, and
    loading a missing variable yields the effective default.
    """

    def __env_options(self, attr: Optional[ISettingAttribute]) -> Any:
        # the entry of the class that declared the member — the nearest at
        # or above it; a member of a hand-built attribute with no
        # declaration record anchors on the reading class
        declaring = None if attr is None else attr.declaring_class
        anchor = declaring if declaring is not None else self.context.settings_class
        return self.context.get_family_options(ENVIRONMENT_METADATA_OPTIONS, anchor)

    def __env_name(self, attr: Optional[ISettingAttribute]) -> str:
        name = None if attr is None else attr.name
        if name:
            # an explicit name= is the full address in the storage — the
            # family's prefix and case never touch it
            return name
        member_name = None if attr is None else attr.bound_name
        if not member_name:
            raise ValueError(
                "the environment variables backend requires either an explicit name= or a "
                "member name to build the environment variable name (dynamic "
                "entries have no attribute)"
            )
        return build_environment_name(member_name, self.__env_options(attr) or {})

    def __env_names(self, attr: Optional[ISettingAttribute]) -> Tuple[str, ...]:
        """The addresses that a flat lookup walks: the primary name, then the
        declared aliases in their order.
        """
        return setting_name_candidates(self.__env_name(attr), attr)

    def __nested(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[SettingMember, Mapping[str, Any]]]:
        """The nested-addressing context of one member; ``None`` when nested
        addressing is off.

        The pair holds the registry entry of the member and the family options. It
        exists only for a member that is governed by the delimiter of the family
        and whose dataclass annotation makes it a nested object.
        """
        member = nested_member(attr, self.context.settings_class)
        if member is None:
            return None
        options = self.__env_options(attr) or {}
        if nested_delimiter_of(options) is None:
            return None
        if nested_object_type(member.annotation) is None:
            return None
        return member, options

    # -- ISettingsSerializer --------------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        nested = self.__nested(attr)
        if nested is not None:
            member, options = nested
            return load_nested_environment_value(
                self.__env_name(attr), member, options, os.environ, _PROCESS_ENVIRONMENT
            )
        options = self.__env_options(attr) or {}
        for env_name in self.__env_names(attr):
            key = environment_key(os.environ, env_name, options, _PROCESS_ENVIRONMENT)
            if key is not None:
                return os.environ[key]
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        env_name = self.__env_name(attr)
        nested = self.__nested(attr)
        if nested is not None:
            member, options = nested
            save_nested_environment_values(
                env_name,
                member,
                options,
                os.environ,
                _PROCESS_ENVIRONMENT,
                value,
                self.to_storage_string,
            )
            return
        options = self.__env_options(attr) or {}
        key = environment_key(os.environ, env_name, options, _PROCESS_ENVIRONMENT)
        # a variable found under a differently-cased spelling is touched
        # under that spelling; a new one lands under the built name
        target = env_name if key is None else key
        if value is None:
            # the storage contract's no-null-form branch: None and absence coincide
            os.environ.pop(target, None)
            return
        # the write direction serves the primary address alone: aliases are
        # read addresses, and the primary one outranks them at every load;
        # a spelling the namespace already holds is the one touched
        os.environ[target] = self.to_storage_string(value)

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        nested = self.__nested(attr)
        if nested is not None:
            member, options = nested
            delete_nested_environment_values(
                self.__env_name(attr), member, options, os.environ, _PROCESS_ENVIRONMENT
            )
            return
        options = self.__env_options(attr) or {}
        # an alias left behind would resurrect the value at the next load
        for env_name in self.__env_names(attr):
            key = environment_key(os.environ, env_name, options, _PROCESS_ENVIRONMENT)
            os.environ.pop(key if key is not None else env_name, None)

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        nested = self.__nested(attr)
        if nested is not None:
            member, options = nested
            return contains_nested_environment_value(
                self.__env_name(attr), member, options, os.environ, _PROCESS_ENVIRONMENT
            )
        options = self.__env_options(attr) or {}
        return any(
            environment_key(os.environ, env_name, options, _PROCESS_ENVIRONMENT) is not None
            for env_name in self.__env_names(attr)
        )

    # -- ISettingNameDescriber -----------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """``environment variable '<name>'``: the variable that this backend reads,
        with the declared aliases listed next to the primary one.
        """
        if attr is None:
            return None
        return spelled_with_aliases(f"environment variable '{self.__env_name(attr)}'", attr.aliases)

    # -- ISourceDescriber --------------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """``("the process environment", None)``: the storage that this backend
        reads. It is not a file, so the designation carries no path.
        """
        return _PROCESS_ENVIRONMENT, None
