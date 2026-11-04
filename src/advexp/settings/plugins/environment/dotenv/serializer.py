# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of the dotenv file backend.

The variable name is ``name=`` when it is given. This is the full address
in the storage, and the options of the family do not change it. Otherwise,
the name is the member name built with the naming options of the family
(the prefix and the case), which are stored per declaring class under the
``ENVIRONMENT_METADATA_OPTIONS`` family key. The entry of the class that
declared the member (the nearest class at or above it) governs the member,
so the own options of a subclass never change the variables of inherited
members.

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
``advexp.settings_base.environment_nested``, and the naming rules are in
``advexp.settings_base.environment_options``. The process environment and a
``.env`` file form one namespace, so a variable that one backend writes
resolves in the same way in the other.

Under ``name_case=NameCase.ANY``, the lookup accepts any spelling of a
built name. The exact spelling wins. If two spellings differ only in case
and none of them matches exactly, the pass fails
(``advexp.settings_base.environment_lookup``).

The file of a pass is chosen in this order: the file named by the
``dotenv_source(...)`` binding of the class (the nearest link along the
settings class chain wins); otherwise the own binding of the class in the
runtime channel; otherwise the module default of
:class:`~advexp.settings.plugins.environment.dotenv.configuration.DotenvConfiguration`
(``.env`` in the working directory). The binding may spell its file as a
template that is filled in from an environment variable, which gives one
file per environment.

A pass reads the file once through the parser of python-dotenv and serves
every operation from that in-memory view. The writes are applied at the end
of the pass through the own line editing of python-dotenv (``set_key`` and
``unset_key``). Lines that the library does not know (comments, unrelated
variables, and their spelling) stay exactly as written, and only the lines
of the saved members change. A CRLF file keeps its line endings: the LF
output of the editor is converted back to the form of the file after the
edit.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union

from advexp.settings.plugin_api import (
    NOT_FOUND,
    PACKAGE_NAME,
    ISettingAttribute,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.settings.plugins.environment.dotenv.configuration import DotenvConfiguration
from advexp.settings_base.dotenv_file import DOTENV_FILE_METADATA
from advexp.settings_base.env_parameter import EnvParameter, resolve_templated_path
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
from advexp.settings_base.module_default import module_default_for
from advexp.settings_base.names import setting_name_candidates, spelled_with_aliases
from advexp.settings_base.setting_member import SettingMember
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.sources import (
    DOTENV_SOURCE_METADATA,
    LINK_FILE_PARAM,
    LINK_PARAMETERS_PARAM,
)

try:
    from dotenv import set_key, unset_key

    from advexp.settings_base.dotenv_parsing import parse_dotenv_variables
except (
    ImportError
) as error:  # pragma: no cover - the environments that run the suite install the extra
    raise ImportError(
        "the dotenv backend requires the python-dotenv package. "
        'Install it with the distribution\'s extra: pip install "advexp-settings[dotenv]"'
    ) from error


class DotenvSerializer(SettingsBaseSerializer):
    """Loads and stores settings in a ``.env`` file parsed by python-dotenv.

    The file has no null form, so for this storage ``None`` and a missing value
    are the same: saving ``None`` removes the line of the variable, and loading
    a missing variable yields the effective default.
    """

    def __init__(self) -> None:
        super().__init__()
        # name-mangled: the pass's file view and its baseline, dispatched
        # through self, kept out of a subclass's reach
        self.__view: Optional[Dict[str, str]] = None
        self.__baseline: Dict[str, str] = {}
        # the file's own line endings: python-dotenv's editor writes LF,
        # and a CRLF file gets its endings restored after the edit
        self.__crlf = False
        # the running pass's mode — what the notifications named — so the
        # write step can tell a save that stored nothing from a delete
        # that removed everything
        self.__pass_mode: Optional[str] = None

    # -- the file ------------------------------------------------------------

    def __source_link(self) -> Optional[SourceLink]:
        """The dotenv source seat in the class's chain; ``None`` when unbound.

        The ``dotenv_source(...)`` binding stores its link there (the file and the
        path parameters), and the file resolution below reads it. A class that the
        builder never bound (a class that uses the module default) has no entry.
        """
        link: Any = self.context.get_class_metadata(DOTENV_SOURCE_METADATA)
        return link if isinstance(link, SourceLink) else None

    def __resolve_file_path(self) -> Path:
        """The file of the pass. The file is chosen in this order: the file of the
        source seat, the own binding of the class, the declaration of the declaring
        module, and finally the module default.

        The path is absolute and is anchored on the settings class. The resolved
        spelling is the key of the anchor, so one class keeps a separate anchor for
        every environment that a templated file produces. The first access of the
        class anchors the exact file, and every pass during the life of the class
        (the views it reads, the diagnostics it quotes, and the writes at the end
        of the passes) keeps using that file, even if the working directory
        changes. Reconfiguring (a new binding, or a new spelling of the module
        default through the ``file_path`` parameter of the plugin) re-anchors the
        file on the next access.
        """
        link = self.__source_link()
        configured: Optional[Union[str, os.PathLike]] = None
        parameters: Optional[Sequence[EnvParameter]] = None
        if link is not None:
            configured = link.param(LINK_FILE_PARAM)
            parameters = link.param(LINK_PARAMETERS_PARAM)
        if configured is None:
            # the seat may exist without a file — a builder called without
            # one — so the class's binding, the module's declaration or the
            # module default serves it, the order the builder's docstring
            # promises
            binding = self.context.get_class_metadata(DOTENV_FILE_METADATA)
            if binding is not None:
                configured = binding
            else:
                declared = module_default_for(
                    DotenvConfiguration,
                    lambda configuration: configuration.file_path,
                    self.context.settings_class.__module__,
                )
                configured = declared if declared is not None else DotenvConfiguration.file_path
        spelling = resolve_templated_path(
            self.context,
            configured,
            parameters,
            f"the dotenv backend ({PACKAGE_NAME})",
        )
        return self.context.anchored_file_path((DOTENV_FILE_METADATA, spelling), spelling)

    def __parse_file(self, path: Path) -> Dict[str, str]:
        """The variables of the file as python-dotenv parses them; an absent file gives
        an empty result.

        The text is read here and passed to the parser as a stream. Because of
        this, an unreadable or undecodable file raises an error, instead of
        producing the silent empty mapping that the parser would return. Quietly
        treating a file that the process cannot read as empty would reset the
        settings. A line with a key and no ``=`` holds no value and addresses
        nothing.

        In a reading pass, both empty outcomes write a debug record. The "miss"
        message of the pass cannot distinguish an absent file, a file that contains
        only comments, and a file that does not contain the variable, and a reader
        who debugs an empty load needs these cases to be told apart. A save pass
        stays quiet about them, because its outcome tells the whole story: the file
        that it creates and fills, or the warning about an empty file. A line that
        python-dotenv cannot parse is a condition of the file itself, so it is
        reported in every pass: the parser hands over its warning, and the warning
        goes to the channel of the family together with the path of the file.
        """
        try:
            # newline="" reads the file's own endings: the text mode's
            # universal-newline translation would fold CRLF to LF before
            # the detection below ever sees it
            with open(path, encoding="utf-8", newline="") as file:
                text = file.read()
        except FileNotFoundError:
            if self.__pass_mode != "save":
                self.context.logger.debug(
                    "the dotenv file %s does not exist, treating it as empty", path
                )
            return {}
        except (OSError, UnicodeError) as exc:
            raise UserFacingError(exc) from exc
        self.__crlf = "\r\n" in text
        if self.__crlf:
            # the parser gets the translated form; the endings are the
            # write step's business, restored after the editor's edit
            text = text.replace("\r\n", "\n")
        variables, problems = parse_dotenv_variables(text)
        for problem in problems:
            self.context.logger.warning("the dotenv file %s: %s", path, problem)
        if not variables and not problems and self.__pass_mode != "save":
            self.context.logger.debug("the dotenv file %s contains no variables", path)
        return variables

    def __file_view(self) -> Dict[str, str]:
        """The variables of the file for the current pass, parsed on the first access
        of the pass.
        """
        view = self.__view
        if view is None:
            view = self.__parse_file(self.__resolve_file_path())
            self.__view = view
            self.__baseline = dict(view)
        return view

    def __restore_crlf(self, path: Path) -> None:
        """Restore the CRLF line endings of a file after the edit of python-dotenv.

        The line editor writes LF, and every line that it rewrites goes through
        that form, so a CRLF file would come out with mixed endings or with LF
        only. The pass reads the result and writes it back with CRLF for every
        newline. It normalizes the endings first, so that nothing is doubled. The
        write is atomic, like the write of the editor itself.
        """
        # newline="" reads the editor's output as written; the restore
        # below flips the endings, and the text mode's translation would
        # have folded what CRLF survived the edit
        with open(path, encoding="utf-8", newline="") as file:
            text = file.read()
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        temp_path = path.with_name(path.name + ".tmp")
        # newline="" writes the text's own endings verbatim: the text
        # mode's translation would undo the CRLF above
        with open(temp_path, "w", encoding="utf-8", newline="") as file:
            file.write(text)
        os.replace(temp_path, path)

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
                "the dotenv file backend requires either an explicit name= or a "
                "member name to build the variable name (dynamic "
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
        env_name = self.__env_name(attr)
        view = self.__file_view()
        nested = self.__nested(attr)
        if nested is not None:
            member, options = nested
            save_nested_environment_values(
                env_name,
                member,
                options,
                view,
                self.__source_label(),
                value,
                self.to_storage_string,
            )
            return
        options = self.__env_options(attr) or {}
        key = environment_key(view, env_name, options, self.__source_label())
        # a variable found under a differently-cased spelling is touched
        # under that spelling; a new one lands under the built name
        target = env_name if key is None else key
        if value is None:
            # the storage contract's no-null-form branch: None and absence coincide
            view.pop(target, None)
            return
        # the write direction serves the primary address alone: aliases are
        # read addresses, and the primary one outranks them at every load;
        # a spelling the namespace already holds is the one touched
        view[target] = self.to_storage_string(value)

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        nested = self.__nested(attr)
        view = self.__file_view()
        if nested is not None:
            member, options = nested
            delete_nested_environment_values(
                self.__env_name(attr), member, options, view, self.__source_label()
            )
            return
        options = self.__env_options(attr) or {}
        # an alias left behind would resurrect the value at the next load
        for env_name in self.__env_names(attr):
            key = environment_key(view, env_name, options, self.__source_label())
            view.pop(key if key is not None else env_name, None)

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

    def synchronize(self) -> None:
        """Write the changes of the pass through the line editing of python-dotenv.

        Each changed variable is written as its own line: a new variable is
        appended, and an existing one is replaced in place. Each removed variable
        loses its line. Every other line of the file stays as written, line endings
        included: a CRLF file gets its endings restored after the LF-writing pass
        of the editor. A view with no changes since the last write writes nothing.

        A save pass that has nothing to write still leaves the file behind. An
        absent file is created empty, which marks the place where the values
        belong, and a warning names the reason why no line was written. The reader
        who called save and expected a file gets both the place and the
        explanation, not silence. A delete pass that ends with an empty file is a
        normal outcome (every line was removed), and it stays quiet.
        """
        view = self.__view
        if view is None:
            return
        path = self.__resolve_file_path()
        if self.__pass_mode == "save" and not view and not self.__baseline:
            # no member put a line into the file: the only value left out
            # is None, which this storage cannot hold; the empty file
            # still names the place, an existing one keeps its lines
            if not path.exists():
                path.touch()
            self.context.logger.warning(
                "the save pass wrote no variables to the dotenv file %s: "
                "every member it serves resolved to None, and None is not "
                "written as a line in this storage",
                path,
            )
        try:
            changed = False
            for name in self.__baseline:
                if name not in view:
                    unset_key(path, name)
                    changed = True
            for name, value in view.items():
                if self.__baseline.get(name) != value:
                    set_key(path, name, value)
                    changed = True
            if self.__crlf and changed:
                self.__restore_crlf(path)
        except OSError as exc:
            # a failed write must reach the user: logging it would pass a
            # save that stored nothing
            raise UserFacingError(exc) from exc
        self.__baseline = dict(view)

    # -- ISettingNameDescriber -----------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """``environment variable '<name>'``: the variable that this backend reads.

        The same variable name also exists in the process environment, which is a
        sibling backend of the family. The caller adds the designation of the
        source next to the address, so the message names the exact file only once.
        """
        if attr is None:
            return None
        return spelled_with_aliases(f"environment variable '{self.__env_name(attr)}'", attr.aliases)

    # -- ISourceDescriber --------------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """``("the dotenv file", <path>)``: the storage that this backend reads.

        The caller lays out the pair. If the address of a member already names the
        file, only the phrase is used, without the path.
        """
        return "the dotenv file", str(self.__resolve_file_path())

    # -- ISerializerNotificationSink -------------------------------------------

    def on_start_serializer_action(self) -> None:
        # a new bracket re-reads the file: edits landing between two passes
        # count, the way python-dotenv itself reads the file fresh each call
        self.__view = None
        self.__baseline = {}
        self.__crlf = False
        self.__pass_mode = None

    def on_end_serializer_action(self) -> None:
        self.__view = None
        self.__baseline = {}
        self.__crlf = False
        self.__pass_mode = None

    def on_start_load_settings(self) -> None:
        # a load bracket names its mode too: the field mirrors the running
        # pass whole, and the write step stays a save-or-delete question
        self.__pass_mode = "load"

    def on_start_save_settings(self) -> None:
        self.__pass_mode = "save"

    def on_start_delete_settings(self) -> None:
        self.__pass_mode = "delete"
