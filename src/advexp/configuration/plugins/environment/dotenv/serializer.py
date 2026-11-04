# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of the dotenv file source.

The variable name is ``name=`` when it is given. This is the full address
in the storage, and the options of the family do not change it. Otherwise,
the name is the member name built with the naming options of the family.
These options are declared on the environment link of the chain
(``env_source(name_prefix=...)`` or ``dotenv_source(name_prefix=...)``) and
are stored per declaring class under the ``ENVIRONMENT_METADATA_OPTIONS``
family key. The rules are the shared vocabulary of the family in
``advexp.settings_base.environment_options``, so a variable that is read by
a settings class and by a configuration class resolves in the same way: the
process environment and a ``.env`` file form one namespace.

The link that the class's chain carries names the file that the source
reads (``dotenv_source(file=...)``). The entry that governs a member
belongs to the class that declared it (the nearest class at or above it),
so the own options of a subclass never change the variables of inherited
members.

Declared ``aliases=`` widen the read. Every alias is a full address, like
``name=``. A load looks up the primary name first, then the aliases in
their order, and the first name found wins. This is how a rename is
migrated: an old variable name keeps serving the member.

A member annotated with a dataclass is a nested object. If the
``nested_delimiter`` option of the family is set, the fields of the object
are addressed through the delimiter and are loaded onto the declared
default as a partial update. Nested addressing is resolved from the primary
name only; aliases take no part in it. The addressing rules live in
``advexp.settings_base.environment_nested``, like the naming rules.

Under ``name_case=NameCase.ANY``, the lookup accepts any spelling of a
built name. The exact spelling wins. If two spellings differ only in case
and none of them matches exactly, the pass fails
(``advexp.settings_base.environment_lookup``).

The source is read-only: it responds to ``load`` and ``contains``. The
write operations of the serializer contract refuse with an error (a
``UserFacingError`` around a ``NotImplementedError`` that names the
source), and the facade of the package never calls them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union

from advexp.configuration.plugin_api import (
    NOT_FOUND,
    PACKAGE_NAME,
    ISettingAttribute,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.settings_base.dotenv_file import DOTENV_FILE_METADATA
from advexp.settings_base.env_parameter import EnvParameter, resolve_templated_path
from advexp.settings_base.environment_lookup import environment_key
from advexp.settings_base.environment_nested import (
    contains_nested_environment_value,
    load_nested_environment_value,
    nested_delimiter_of,
    nested_member,
    nested_object_type,
)
from advexp.settings_base.environment_options import (
    ENVIRONMENT_METADATA_OPTIONS,
    build_environment_name,
)
from advexp.settings_base.names import setting_name_candidates, spelled_with_aliases
from advexp.settings_base.setting_member import SettingMember
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.source_link_sink_interface import ISourceLinkSink
from advexp.settings_base.sources import LINK_FILE_PARAM, LINK_PARAMETERS_PARAM

try:
    from advexp.settings_base.dotenv_parsing import parse_dotenv_variables
except (
    ImportError
) as error:  # pragma: no cover - the environments that run the suite install the extra
    raise ImportError(
        "the dotenv source requires the python-dotenv package. "
        'Install it with the distribution\'s extra: pip install "advexp-configuration[dotenv]"'
    ) from error


class DotenvSerializer(SettingsBaseSerializer, ISourceLinkSink):
    """Loads configuration from a ``.env`` file parsed by python-dotenv.

    The file has no null form, so for this source ``None`` and a missing value
    are the same: a missing variable yields the effective default of the
    member. A pass reads the file once and serves every member from that view.
    Lines that the source does not know are ignored and left as they are: the
    file belongs to whoever writes it.
    """

    def __init__(self) -> None:
        super().__init__()
        # name-mangled: the pass state dispatched through self, kept out
        # of a subclass's reach
        self.__view: Optional[Mapping[str, str]] = None
        self.__file: Optional[Union[str, os.PathLike]] = None
        self.__parameters: Optional[Tuple[EnvParameter, ...]] = None

    # -- ISourceLinkSink --------------------------------------------------------

    def set_source_link(self, link: SourceLink) -> None:
        """``ISourceLinkSink`` delivery: the link that this source reads.

        The ``file=`` of the link names the ``.env`` file. It may contain template
        slots, which are resolved through the ``parameters=`` of the link. The
        naming options arrive in a different way: through the shared dictionary of
        the family.
        """
        self.__file = link.param(LINK_FILE_PARAM)
        self.__parameters = link.param(LINK_PARAMETERS_PARAM)

    # -- the file ------------------------------------------------------------

    def __resolve_file_path(self) -> Path:
        """The file of the link that this serializer serves.

        The path is absolute and is anchored on the configuration class. The first
        access of the class anchors the exact file, and every pass during the life
        of the class (the views it reads, the diagnostics it quotes) keeps using
        that file, even if the working directory changes. The anchor is kept per
        resolved link file: two links of one chain that read two files keep
        separate anchors, and a templated link anchors the file of each
        environment under the file that it resolved to.
        """
        configured = self.__file
        if configured is None:
            raise UserFacingError(
                ValueError(
                    "the dotenv file source has no file to read: the link was "
                    f"built without one (dotenv_source(file=...) spells it, {PACKAGE_NAME})"
                )
            )
        resolved = resolve_templated_path(
            self.context,
            configured,
            self.__parameters,
            f"the dotenv file source ({PACKAGE_NAME})",
        )
        return self.context.anchored_file_path((DOTENV_FILE_METADATA, resolved), resolved)

    def __file_view(self) -> Mapping[str, str]:
        """The variables of the file for the current pass, parsed on the first access
        of the pass.

        The text is read here and passed to the parser of python-dotenv as a
        stream. Because of this, an unreadable or undecodable file raises an
        error, instead of producing the silent empty mapping that the parser would
        return. Quietly treating a file that the process cannot read as empty
        would report every member as missing. A line with a key and no ``=`` holds
        no value and addresses nothing.

        Both empty outcomes write a debug record. The "miss" message of the pass
        cannot distinguish an absent file, a file that contains only comments, and
        a file that does not contain the variable, and a reader who debugs an empty
        load needs these cases to be told apart. A line that python-dotenv cannot
        parse is a condition of the file itself: the parser hands over its warning,
        and the warning goes to the channel of the family together with the path of
        the file.
        """
        view = self.__view
        if view is not None:
            return view
        path = self.__resolve_file_path()
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            # an absent file is an empty source: required members report,
            # defaults stand in
            self.context.logger.debug(
                "the dotenv file %s does not exist, treating it as empty", path
            )
            view = {}
        except (OSError, UnicodeError) as exc:
            raise UserFacingError(exc) from exc
        else:
            variables, problems = parse_dotenv_variables(text)
            for problem in problems:
                self.context.logger.warning("the dotenv file %s: %s", path, problem)
            view = variables
            if not view and not problems:
                self.context.logger.debug("the dotenv file %s contains no variables", path)
        self.__view = view
        return view

    def __env_options(self, attr: Optional[ISettingAttribute]) -> Any:
        # the entry of the class that declared the member (the nearest at
        # or above it); a member of a hand-built attribute with no
        # declaration record anchors on the reading class
        declaring = None if attr is None else attr.declaring_class
        anchor = declaring if declaring is not None else self.context.settings_class
        return self.context.get_family_options(ENVIRONMENT_METADATA_OPTIONS, anchor)

    def __env_name(self, attr: Optional[ISettingAttribute]) -> str:
        name = None if attr is None else attr.name
        if name:
            # an explicit name= is the full address in the storage: the
            # family's prefix and case never touch it
            return name
        member_name = None if attr is None else attr.bound_name
        if not member_name:
            raise ValueError(
                "the dotenv file source requires either an explicit name= or a "
                "member name to build the variable name"
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

        The tuple holds the registry entry of the member and the family options.
        It exists only for a member that is governed by the delimiter of the family
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

    def __source_label(self) -> str:
        """The phrase that names the file in the error message of a lookup conflict."""
        return f"the dotenv file '{self.__resolve_file_path()}'"

    # -- ISettingsSerializer --------------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        nested = self.__nested(attr)
        if nested is not None:
            member, options = nested
            return load_nested_environment_value(
                self.__env_name(attr),
                member,
                options,
                self.__file_view(),
                self.__source_label(),
            )
        view = self.__file_view()
        options = self.__env_options(attr) or {}
        for env_name in self.__env_names(attr):
            key = environment_key(view, env_name, options, self.__source_label())
            if key is not None:
                return view[key]
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """Refused with an error: a read-only source never writes.

        The facade of the package never calls this operation, so a caller that
        reaches it has mistaken the source for a storage backend. The refusal says
        so, instead of a silent no-op that would hide the bug.
        """
        raise UserFacingError(
            NotImplementedError(
                f"the dotenv file source is read-only: it loads and never writes ({PACKAGE_NAME})"
            )
        )

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        """Refused with an error: a read-only source never deletes.

        The facade of the package never calls this operation, so a caller that
        reaches it has mistaken the source for a storage backend. The refusal says
        so, instead of a silent no-op that would hide the bug.
        """
        raise UserFacingError(
            NotImplementedError(
                f"the dotenv file source is read-only: it loads and never deletes ({PACKAGE_NAME})"
            )
        )

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        nested = self.__nested(attr)
        if nested is not None:
            member, options = nested
            return contains_nested_environment_value(
                self.__env_name(attr),
                member,
                options,
                self.__file_view(),
                self.__source_label(),
            )
        view = self.__file_view()
        options = self.__env_options(attr) or {}
        return any(
            environment_key(view, env_name, options, self.__source_label()) is not None
            for env_name in self.__env_names(attr)
        )

    # -- ISettingNameDescriber -----------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """``environment variable '<name>'``: the variable that this source reads.

        The same variable name also exists in the process environment, which is a
        sibling source of the family. The caller adds the designation of the source
        next to the address, so the message names the exact file only once.
        """
        if attr is None:
            return None
        return spelled_with_aliases(f"environment variable '{self.__env_name(attr)}'", attr.aliases)

    # -- ISourceDescriber --------------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """``("the dotenv file", <path>)``: the storage that this source reads.

        This package serves declared members only, so a dynamic entry has no place
        in it. The caller lays out the pair. If the address of a member already
        names the file, the phrase is used alone.
        """
        return "the dotenv file", str(self.__resolve_file_path())

    # -- ISerializerNotificationSink -------------------------------------------

    def on_start_serializer_action(self) -> None:
        # a new bracket re-reads the file: edits landing between two passes
        # count, the way python-dotenv itself reads the file fresh each call
        self.__view = None

    def on_end_serializer_action(self) -> None:
        self.__view = None
