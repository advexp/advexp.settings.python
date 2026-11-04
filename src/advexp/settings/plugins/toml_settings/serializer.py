# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of the TOML file backend.

The file is one TOML document that is owned by the library.

A setting is stored at the address that its key names. The key is the
explicit ``name=`` or the name built by the key pattern of the binding
(``toml_source(name_pattern=...)``; the full ``{module}.{class}.{member}``
pattern by default). Every dot in the key separates a table level, and the
last part is the key. This is the same address that TOML itself reads:
``a.b.c = v`` and ``[a.b] c = v`` name one place, so the written file
contains no quoted dotted keys. A key without a dot is a plain key, and a
literal key that contains a dot is reached through a ``path=`` segment,
which is never split.

Values are native TOML: ``datetime``, ``date`` and ``time`` values stay
native in the file (the form that TOML itself uses), and every other
round-trip type takes its usual stored form.

The optional ``path=`` of
:class:`~advexp.settings.plugins.toml_settings.setting.TOMLSetting` locates a
key in the document tree as a JSON Pointer (RFC 6901): a leading ``/`` and
slash-separated segments with ``~1``/``~0`` escaping.
``TOMLSetting(name="host", path="/net/proxy")`` stores the key inside
``[net.proxy]``, and ``path="/mirrors/1"`` stores it inside the second
element of the ``mirrors`` array. A segment that consists only of digits
indexes an array if the node it steps into is an array, and names a table
key otherwise. An array grows only by one element at its tail, which is the
position that the write fills itself. A position further out would need a
gap, and TOML has no null to fill it with. An emptied array element stays
as the empty table that it becomes, so its siblings keep their positions.

Declared ``aliases=`` widen the read. Every alias is a full address of its
own, and its dots nest in the same way. A load looks up the primary address
first, then the aliases in their order (each one placed by the same
``path=``), and the first address found wins. Saving writes only the primary
address. Deleting also drops the alias leaves, so a deleted member cannot
come back through an old address.

Dynamic entries (the calls that carry ``attr=None``) are stored in their own
section of the document, grouped per settings class; see
:attr:`~advexp.settings.plugin_api.DocumentDynamicSettingsPlugin.dynamic_settings_section_name`.
The class part of the address is nested by its dots in the same way, and
the name of an entry is stored as one plain literal key. A name that is
given at runtime may be any text, and nesting it would make a table value of
an entry (a dataclass, say) indistinguishable from a deeper level. If the
section is disabled, the entries fall back to flat ``D``-prefixed full-name
keys at the document root. Their names are built from the own name pattern
parameter of the dynamic side (``TOMLDynamicSettingsConfiguration.name_pattern``),
which the static passes also read: the section reservation and the
enumeration below use its class part.

The section shares the file of the static members, unless the binding of the
class moves the entries to a file of their own (the ``dynamic_file=`` of
``toml_source(...)``, the per-class binding of the dynamic side, or the
module-wide ``TOMLDynamicSettingsConfiguration.file_path``). The two files
then hold independent documents, and the location of the section in the
static file is no longer reserved.

A class that is bound through ``toml_source(file=...)`` may spell its file,
and the file of its dynamic entries, as a template that is filled in from an
environment variable: ``toml_source(file="settings-{APP_ENV}.toml",
parameters=env_parameter("APP_ENV", ...))`` reads and writes the file of one
environment, and the values always return to the file that they were loaded
from.

A pass reads the document once, applies its changes in memory, and writes
the file back atomically at the end (a temporary file is renamed over the
old one; the rename re-creates the file, and the write copies the
permission mode to the temporary file, so a mode that was set by hand
survives). The editor is tomlkit, which preserves the format: the comments,
blank lines, key order, and line endings of the file survive a save, a new
key is added at the end of its table, and a pass that changed nothing writes
exactly the same bytes.

The document of a file is shared by every serializer over that file. For
example, a settings class can mix attribute classes (the stock
``TOMLSetting`` and a registered subclass, say); all of them then flush one
consistent document, instead of two private views that drop each other's
keys. The shared entry lives only inside the pass brackets, so a later pass
re-reads the file. Keys that the library does not know are preserved as
they are.

TOML has no null. Storing ``None`` removes the entry, and the next load
falls back to the default (this is the rule of the serializer contract for a
storage without a null form). A ``None`` nested inside a container is
refused, because dropping one position inside an array would change the
address of every sibling.
"""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

try:
    import tomlkit
    from tomlkit.container import Container
    from tomlkit.exceptions import ParseError
    from tomlkit.items import AoT, Table
except (
    ImportError
) as error:  # pragma: no cover - the environments that run the suite install the extra
    raise ImportError(
        "the TOML backend requires the tomlkit package. "
        'Install it with the distribution\'s extra: pip install "advexp-settings[toml]"'
    ) from error

from advexp.settings.plugin_api import (
    NOT_FOUND,
    PACKAGE_NAME,
    DocumentDynamicSettingsPlugin,
    IDynamicSettingsInfo,
    ISettingAttribute,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.settings.plugins.toml_settings.configuration import TOMLSettingsConfiguration
from advexp.settings.plugins.toml_settings.dynamic_configuration import (
    TOMLDynamicSettingsConfiguration,
)
from advexp.settings.plugins.toml_settings.setting import TOMLSetting
from advexp.settings_base.dynamic_document import (
    document_dynamic_plugin,
    dynamic_entry_placement,
    dynamic_section_segments,
    dynamic_settings_names,
    resolve_dynamic_document_file,
)
from advexp.settings_base.env_parameter import resolve_templated_path
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.module_default import module_default_for
from advexp.settings_base.names import (
    DEFAULT_SETTINGS_NAME_PATTERN,
    get_dynamic_settings_class_prefix,
    get_full_setting_name,
    setting_name_candidates,
    spelled_with_aliases,
)
from advexp.settings_base.pointer import array_index, pointer_display, pointer_steps
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.sources import (
    LINK_FILE_PARAM,
    LINK_NAME_PATTERN_PARAM,
    LINK_PARAMETERS_PARAM,
    TOML_SOURCE_METADATA,
)
from advexp.settings_base.toml_file import TOML_DYNAMIC_FILE_METADATA, TOML_FILE_METADATA
from advexp.settings_base.toml_options import (
    TOML_METADATA_OPTIONS,
    TOML_TABLE_SEPARATOR,
    toml_name_pattern,
    toml_table_levels,
)

_FILE_LOCK = threading.RLock()
"""Serializes file reads/writes and the shared-document registry of
concurrently running passes."""

_SHARED_DOCUMENTS: Dict[Path, "_SharedDocument"] = {}


def _file_chmod(path: Path) -> Optional[int]:
    """The ``chmod`` bits of the file; ``None`` for a file that does not exist.

    The write gives them to the temporary file before the rename, as the own
    editor of python-dotenv does: a re-created file must not lose the
    permission bits that its reader set (for example, 600 on a file with
    secrets).
    """
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        return None


"""The in-memory document of each file in active use, keyed by the file
path (guarded by ``_FILE_LOCK``)."""


def _file_parameter(holder: type) -> str:
    """The holder's file parameter spelled for the error messages."""
    return f"{holder.__module__}.{holder.__qualname__}.file_path"


def _emptied_container(node: Any) -> bool:
    """Return whether ``node`` is a container that the pass has emptied while
    removing a key.

    This is a table with no keys left, an array with no elements, or an array in
    which every element is itself emptied. The recursive form is needed for an
    array of emptied tables. A scalar is never emptied: it is data that the
    library does not own.
    """
    if isinstance(node, dict):
        return not node
    if isinstance(node, list):
        return all(_emptied_container(item) for item in node)
    return False


class _SharedDocument:
    """The document of one settings file, shared by the serializers that read and
    write it.

    ``users`` counts the serializers that have joined. The entry stays in the
    registry while at least one of them is inside its pass brackets, and the
    last one to leave removes it. The next pass then re-reads the file.

    ``dirty`` lives on the entry, not on a serializer: whoever flushes first
    writes every pending change of the pass, and the next flush inside the same
    brackets finds nothing left to write.

    ``crlf`` holds the line endings of the file: a CRLF file keeps them through
    a flush. ``chmod`` holds the permission bits of the file, which are given to
    the temporary file before the rename.
    """

    __slots__ = ("path", "document", "users", "dirty", "crlf", "chmod")

    def __init__(
        self, path: Path, document: Dict[str, Any], crlf: bool, chmod: Optional[int]
    ) -> None:
        self.path = path
        self.document = document
        self.users = 0
        self.dirty = False
        self.crlf = crlf
        self.chmod = chmod


class TOMLSettingsSerializer(SettingsBaseSerializer, IDynamicSettingsInfo):
    """Loads and stores settings in a TOML file keyed by setting-name addresses.

    Every key is stored at the address that it names: its dot-separated parts
    are table levels, and the last part is the key. A ``path=`` on the
    attribute locates the key deeper in the document tree as a JSON Pointer. A
    path segment that consists only of digits indexes an array if the node it
    steps into is an array, and names a table key otherwise.

    Dynamic entries (the ``attr=None`` calls) are stored in the dynamic section
    of the document, with one table per settings class, and they are
    enumerated through :meth:`get_dynamic_settings_names`. The placement of
    every key is built by the :meth:`_setting_segments` hook, which is the
    placement extension point of the backend.
    """

    def __init__(self) -> None:
        super().__init__()
        # name-mangled: the pass state dispatched through self, kept out
        # of a subclass's reach
        self.__shared: Optional[_SharedDocument] = None

    # -- document handling ---------------------------------------------------

    def __source_link(self) -> Optional[SourceLink]:
        """The TOML source seat in the class's chain; ``None`` when unbound.

        The ``toml_source(...)`` binding stores its link there (the file, the key
        pattern, and the path parameters), and every resolution of a file or a name
        in this serializer reads it. A class that the builder never bound (a class
        that uses the module default) has no entry.
        """
        link: Any = self.context.get_class_metadata(TOML_SOURCE_METADATA)
        return link if isinstance(link, SourceLink) else None

    def __unfolded(self, configured: Union[str, os.PathLike]) -> str:
        """The configured spelling with its template slots resolved.

        A class that is bound through ``toml_source`` resolves its templated paths
        (the static file and the dynamic file) through the path parameters of the
        link, using the reading of each variable in the current pass. A spelling
        without parameters is returned as given.
        """
        link = self.__source_link()
        if link is None:
            return os.fspath(configured)
        return resolve_templated_path(
            self.context,
            configured,
            link.param(LINK_PARAMETERS_PARAM),
            f"the TOML settings backend ({PACKAGE_NAME})",
        )

    def __resolve_file_path(self, dynamic: bool) -> Path:
        """The file of the side that the pass works on: dynamic entries or static
        members.

        A serializer instance may serve either side during its life (a bracket
        holds only one side: the pipeline drives the static members, and the
        dynamic plugin drives the dynamic entries), and the two sides may name
        different files.

        The path is absolute and is anchored on the settings class, each side under
        its own anchor. The resolved spelling is the key of the anchor, so one class
        keeps a separate anchor for every environment that a templated file
        produces. The first access of the class anchors the exact file, and every
        pass during the life of the class (the documents it reads, the diagnostics
        it quotes, and the writes at the end of the passes) keeps using that file,
        even if the working directory changes. Reconfiguring (a new binding, or a
        new spelling of the module default) re-anchors the file on the next access.
        """
        configured = self.__resolve_configured_path(dynamic)
        spelling = self.__unfolded(configured)
        anchor_key = TOML_DYNAMIC_FILE_METADATA if dynamic else TOML_FILE_METADATA
        return self.context.anchored_file_path((anchor_key, spelling), spelling)

    def __static_configured_path(self) -> Optional[Union[str, os.PathLike]]:
        """The configured spelling of the static side; ``None`` when unset.

        The levels, from the nearest to the widest: the ``toml_source`` binding of
        the class (its file), the static per-class binding (the runtime channel),
        the declaration of the declaring module, and the module default of
        ``TOMLSettingsConfiguration``.
        """
        link = self.__source_link()
        if link is not None:
            file = link.param(LINK_FILE_PARAM)
            if file is not None:
                return file
        binding = self.context.get_class_metadata(TOML_FILE_METADATA)
        if binding is not None:
            return binding
        declared = module_default_for(
            TOMLSettingsConfiguration,
            lambda configuration: configuration.file_path,
            self.context.settings_class.__module__,
        )
        return declared if declared is not None else TOMLSettingsConfiguration.file_path

    def __resolve_configured_path(self, dynamic: bool) -> Union[str, os.PathLike]:
        # resolution order: the dynamic side's own file (the per-class
        # binding, then the module declaration, then the module default;
        # dynamic passes only) -> the static side's levels (the class's
        # toml_source binding, the static per-class binding, the static
        # module declaration, the static module default)
        if dynamic:
            own = resolve_dynamic_document_file(
                self.context,
                dynamic_file_metadata=TOML_DYNAMIC_FILE_METADATA,
                module_default_holder=TOMLDynamicSettingsConfiguration,
                static_levels=self.__static_configured_path,
            )
            if own is not None:
                return own
            # configuration errors must reach the user: the pipeline logs and
            # skips ordinary exceptions during a load pass
            raise UserFacingError(
                ValueError(
                    "TOML settings file for dynamic settings is not configured: "
                    f"set {_file_parameter(TOMLDynamicSettingsConfiguration)} (an own "
                    "file for the dynamic entries, declared with for_this_module "
                    "or set process-wide), bind "
                    f"{self.__class_name()} to one with "
                    "options=toml_source(dynamic_file=...), or configure the "
                    f"static file ({_file_parameter(TOMLSettingsConfiguration)} or "
                    "options=toml_source(...))"
                )
            )
        configured = self.__static_configured_path()
        if configured is None:
            # configuration errors must reach the user: the pipeline logs and
            # skips ordinary exceptions during a load pass
            raise UserFacingError(
                ValueError(
                    "TOML settings file is not configured: set "
                    f"{_file_parameter(TOMLSettingsConfiguration)} for the declaring "
                    "module (for_this_module) or process-wide, or bind "
                    f"{self.__class_name()} to its own file with options=toml_source(...)"
                )
            )
        return configured

    def __dynamic_shares_static_file(self) -> bool:
        """Return whether the dynamic entries go into the file of the static members.

        The result is ``False`` once the own file of the dynamic side (the
        per-class binding or the module default) names another file. The static
        document then holds no dynamic section, so static keys may freely use its
        location. A path that names the same file as the static side is the shared
        case again: one document, one reservation.
        """
        return self.__resolve_file_path(True) == self.__resolve_file_path(False)

    def __class_name(self) -> str:
        return self.context.settings_class.__name__

    # -- name building ------------------------------------------------------

    def __toml_options(self, attr: ISettingAttribute) -> Mapping[str, Any]:
        # the entry of the class that declared the member — the nearest at
        # or above it; a member of a hand-built attribute with no
        # declaration record anchors on the reading class
        declaring = attr.declaring_class
        anchor = declaring if declaring is not None else self.context.settings_class
        return self.context.get_family_options(TOML_METADATA_OPTIONS, anchor) or {}

    def __static_key(self, setting_name: str, attr: ISettingAttribute) -> str:
        """The document key that the pass addresses for the member.

        An explicit ``name=`` is the full address in the document, exactly as
        delivered. The key of every other member is built from the key pattern: the
        ``toml_source(name_pattern=...)`` that the class is bound through, or the
        per-class entry of the family for a class that uses the module default. The
        key is built by the shared name builder, so the name wishes of the
        serializer apply to these keys in the same way as to the default spelling.
        """
        if attr.name:
            return setting_name
        member_name = attr.bound_name
        if not member_name:
            raise ValueError(
                "the TOML file backend requires either an explicit name= or a member "
                "name to build the document key (dynamic entries have no "
                "attribute)"
            )
        link = self.__source_link()
        if link is not None:
            pattern: Optional[str] = link.param(LINK_NAME_PATTERN_PARAM)
        else:
            pattern = toml_name_pattern(self.__toml_options(attr))
        return get_full_setting_name(
            member_name,
            attr,
            self.context.settings_class,
            self,
            pattern=pattern or DEFAULT_SETTINGS_NAME_PATTERN,
        )

    def __storage_key(self, setting_name: str, attr: Optional[ISettingAttribute]) -> str:
        """The key that the storage operations work with: the delivered name for a
        dynamic entry, and the key built by the family for a static member.
        """
        if attr is None:
            return setting_name
        return self.__static_key(setting_name, attr)

    def __candidate_keys(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Tuple[str, ...]:
        """The keys that a lookup walks: the primary key, then the declared aliases in
        their order. Every alias is a full address of its own.
        """
        return setting_name_candidates(self.__storage_key(setting_name, attr), attr)

    def __dynamic_name_pattern(self) -> str:
        """The name pattern of the dynamic side: a parameter of its configuration."""
        return TOMLDynamicSettingsConfiguration.name_pattern

    def __load_document(self, path: Path) -> Tuple[Dict[str, Any], bool, Optional[int]]:
        """The parsed document of the file, with its detected line endings; an absent
        file gives an empty document.

        An empty or whitespace-only file is parsed as an empty document. TOML allows
        this, so a blank file is not an anomaly, unlike in JSON. Empty results are
        logged at debug level. The "miss" message of the pass cannot distinguish an
        absent file, an empty document, and a document that does not contain the
        key, and a reader who debugs an empty load needs these cases to be told
        apart.
        """
        try:
            # newline="" reads the file's own endings: the text mode's
            # universal-newline translation would fold CRLF to LF before
            # the detection below ever sees it
            with open(path, encoding="utf-8", newline="") as file:
                text = file.read()
        except FileNotFoundError:
            self.context.logger.debug("the TOML file %s does not exist, treating it as empty", path)
            return {}, False, None
        except OSError as exc:
            # an unreadable-but-present file (permissions, a non-directory on
            # the path) must reach the user: silently falling back to an
            # empty document would reset the settings
            raise UserFacingError(exc) from exc
        except UnicodeError as exc:
            # an undecodable file (a UTF-16 one, say) must reach the user
            # the same way; the bare codec message names neither the
            # library, the file nor the pass, so the wrapper carries the
            # phrase
            raise UserFacingError(
                ValueError(f"{PACKAGE_NAME}: cannot read the TOML settings file {path}: {exc}")
            ) from exc
        if text.startswith(UTF8_BOM):
            # a BOM-prefixed file is its own condition, not a parse
            # puzzle: TOML requires plain UTF-8, and letting the parser
            # speak would only mutter about an empty key
            raise UserFacingError(
                ValueError(
                    f"{PACKAGE_NAME}: cannot read the TOML settings file {path}: "
                    "it starts with a UTF-8 BOM, and a TOML file must be plain UTF-8"
                )
            )
        # line endings are the file's own too: a CRLF file keeps them,
        # and the flush writes them back. The parser gets the translated
        # form — its document renders LF, and the flip at the flush
        # restores the file's endings whole
        crlf = "\r\n" in text
        if crlf:
            text = text.replace("\r\n", "\n")
        try:
            document = tomlkit.parse(text)
        except ParseError as exc:
            # a corrupt settings file must reach the user, not fall back
            # to defaults silently; the package name names the library as
            # the source, the path names the file, and "TOML settings
            # file" names the pass that read it — the bare parser message
            # names none of the three
            raise UserFacingError(
                ValueError(f"{PACKAGE_NAME}: cannot parse the TOML settings file {path}: {exc}")
            ) from exc
        if not document:
            self.context.logger.debug("the TOML file %s contains no keys", path)
        return document, crlf, _file_chmod(path)

    def __shared_document(self, path: Path) -> _SharedDocument:
        """The shared document entry of this file; the serializer joins it on first
        access.

        The first access over a file loads it into the registry. Every further
        serializer over the same file (for example, the attribute-class serializers
        of one mixed settings class, or a concurrent pass) joins that entry, so all
        of them change and flush one document. A join holds the entry until
        ``on_end_serializer_action`` releases it. A bracket works on one file, so a
        single joined slot is enough.
        """
        entry = self.__shared
        if entry is None:
            with _FILE_LOCK:
                entry = _SHARED_DOCUMENTS.get(path)
                if entry is None:
                    entry = _SharedDocument(path, *self.__load_document(path))
                    _SHARED_DOCUMENTS[path] = entry
                entry.users += 1
                self.__shared = entry
        return entry

    def __document_or_load(self, path: Path) -> Dict[str, Any]:
        return self.__shared_document(path).document

    def __synchronize_document(self) -> None:
        entry = self.__shared
        if entry is None or not entry.dirty:
            return
        text = tomlkit.dumps(entry.document)
        if not text.endswith("\n"):
            text += "\n"
        if entry.crlf:
            # the file's own line endings: normalize first, then flip
            # every newline to CRLF — a CRLF already sitting inside a
            # written multiline string must not double
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        try:
            with _FILE_LOCK:
                entry.path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = entry.path.with_name(entry.path.name + ".tmp")
                # newline="" writes the text's own endings verbatim: the
                # text mode's translation would undo the CRLF above (and
                # on Windows it would impose its own on everyone)
                with open(temp_path, "w", encoding="utf-8", newline="") as file:
                    file.write(text)
                if entry.chmod is not None:
                    # the replace re-creates the file: the temp one takes
                    # the old bits over, or a hand-set one would not
                    # survive the save
                    os.chmod(temp_path, entry.chmod)
                os.replace(temp_path, entry.path)
        except OSError as exc:
            # a failed write must reach the user: logging it would pass a
            # save that stored nothing
            raise UserFacingError(exc) from exc
        entry.dirty = False

    # -- name paths ----------------------------------------------------------

    def __dynamic_plugin(self) -> Optional[DocumentDynamicSettingsPlugin]:
        """The dynamic plugin pinned to this backend; ``None`` when the dynamic
        package is not imported.

        The lookup goes through the context, using the pin built from the
        attribute class of this backend. The plugin package imports this module for
        its binding, so importing the plugin class here would be circular. The pin
        lookup is the route without a cycle to the section parameters of the
        plugin.
        """
        return document_dynamic_plugin(self.context, TOMLSetting)

    def __dynamic_section_segments(self) -> Optional[List[str]]:
        """Location segments of the dynamic section; ``None`` means flat keys.

        The location is the section name plus, when it is bound, the segments of
        the section path (the ``name=``/``path=`` pair of the dynamic plugin). Each
        parameter resolves along the MRO of the settings class to the most derived
        explicit binding, and it falls back to the defaults of the plugin. If the
        plugin was never imported, the default location stays reserved. The shared
        resolution lives in the document-side module of the family.
        """
        return dynamic_section_segments(self.context, self.__dynamic_plugin())

    def __dynamic_segments(self, setting_name: str, path: Path) -> List[str]:
        """Location of a dynamic entry: the section, the class, the name."""
        placement = dynamic_entry_placement(
            self.context,
            self.__dynamic_plugin(),
            self,
            setting_name,
            self.__dynamic_name_pattern(),
            path,
        )
        if placement.section is None:
            # the flat layout: the full name is the key
            return [setting_name]
        # the class part nests like every key (its dots are table levels);
        # the entry's own name is one literal key — a runtime-given name
        # may be any text, and nesting it would make a table value of an
        # entry indistinguishable from a deeper level
        return [
            *placement.section,
            *toml_table_levels(placement.class_key),
            placement.plain_name,
        ]

    @staticmethod
    def __locations_overlap(left: Sequence[str], right: Sequence[str]) -> bool:
        """Whether one location is an ancestor of (or equal to) the other."""
        shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
        return longer[: len(shorter)] == shorter

    def _setting_segments(self, setting_name: str, attr: Optional[ISettingAttribute]) -> List[str]:
        """Location segments of an entry in the document: the placement hook.

        Every storage operation (``load``, ``save``, ``delete``, ``contains``)
        locates its key through this method. This makes it the placement extension
        point of the backend: a protected hook of the inheritance contract, which
        subclasses override (calling ``super()`` to get the stock placement) to
        relocate keys at runtime. Outside code does not call it.

        The ``setting_name`` that the hook receives is the document key of the
        entry, as the caller resolved it: an explicit ``name=`` or the key built by
        the family pattern for a static member, and the full name built by the
        pattern of the dynamic side for a dynamic entry. The stock placement splits
        that key on the dot (the table separator of TOML) into table levels below
        the ``path=`` segments
        (:func:`advexp.settings_base.toml_options.toml_table_levels`), so the key is
        stored at the address that it names, and the written file contains no
        quoted dotted keys.

        A dynamic entry (``attr is None``) is routed to its section: the class part
        of the address is nested in the same way, and the name of the entry is a
        plain literal key. A static entry follows the ``path=`` segments of the
        attribute, with the levels of the key last.

        The reservation check belongs to the base implementation: the base raises
        an error when its placement would land inside the dynamic settings section.
        An override that bypasses ``super()`` also bypasses this check, and it is
        then responsible for keeping clear of the section.
        """
        if attr is None:
            return self.__dynamic_segments(setting_name, self.__resolve_file_path(True))
        setting = self.attribute_of(attr, TOMLSetting)
        path = setting.path if setting is not None else None
        segments: List[str]
        if path is None:
            segments = toml_table_levels(setting_name)
        else:
            segments = pointer_steps(path)
            segments.extend(toml_table_levels(setting_name))
        section = self.__dynamic_section_segments()
        if (
            section is not None
            and self.__locations_overlap(section, segments)
            # the reservation holds in the file that carries the section: with
            # the dynamic entries in a file of their own, the static document
            # has no section to collide with
            and self.__dynamic_shares_static_file()
        ):
            # the section location is the library's own layout; letting a
            # static setting overwrite (or nest inside) it would destroy it
            raise UserFacingError(
                ValueError(
                    f"Cannot store setting {setting_name!r} in "
                    f"{self.__resolve_file_path(False)}: {pointer_display(section)!r} is "
                    "reserved for the dynamic settings section"
                )
            )
        return segments

    def __read_container(self, segments: List[str], path: Path) -> Optional[Dict[str, Any]]:
        """The table that holds the leaf key, or ``None`` where the path breaks off.

        A segment that consists only of digits reads an array position if the node
        it steps into is a list, and a table key otherwise. The path breaks off at
        a missing key, an out-of-range position, or a scalar in the middle of the
        path.
        """
        node: Any = self.__document_or_load(path)
        for segment in segments[:-1]:
            index = array_index(segment)
            if isinstance(node, list):
                if index is None or index >= len(node):
                    return None
                node = node[index]
            elif isinstance(node, dict):
                node = node.get(segment)
            else:
                return None
        if not isinstance(node, dict):
            return None
        return node

    def __write_container(
        self, setting_name: str, segments: List[str], path: Path
    ) -> Dict[str, Any]:
        """The table that holds the leaf key; missing containers are created along the
        way.

        A missing table on the path is created. The next segment decides what it
        becomes: a segment that consists only of digits (and is not the leaf, which
        is always a key) makes an array to index into, and any other segment makes a
        table. An array on the path grows only by one element at its tail, which is
        the position that this write fills itself. A position further out would
        need a gap between the elements, and TOML has no null to fill it with.
        """
        node: Any = self.__document_or_load(path)
        owner = "the document root"
        blank_first_row = False  # set when this walk creates an array of tables
        for position, segment in enumerate(segments[:-1]):
            index = array_index(segment)
            wants_array = (
                position + 1 < len(segments) - 1 and array_index(segments[position + 1]) is not None
            )
            accessor: Union[int, str]
            if isinstance(node, list):
                if index is None:
                    # a non-index segment cannot step into an array; the
                    # array itself is data the library does not own
                    raise UserFacingError(
                        ValueError(
                            f"Cannot store setting {setting_name!r} in "
                            f"{path}: {owner} on its path "
                            "holds a list, not an object"
                        )
                    )
                if index == len(node):
                    # the tail position: the array grows by the one element
                    # this write is about to fill — no gap ever opens. A
                    # table slot of an array of tables takes a real table —
                    # a plain dict loses the blank line tomlkit puts before
                    # a [[row]]; an inline array's slot stays a plain dict:
                    # a table inside one renders broken TOML.
                    if wants_array:
                        node.append([])
                    elif isinstance(node, AoT):
                        row: Any = tomlkit.table()
                        if blank_first_row and not node:
                            row.trivia.indent = "\n"
                        node.append(row)
                    else:
                        node.append({})
                elif index > len(node):
                    raise UserFacingError(
                        ValueError(
                            f"Cannot store setting {setting_name!r} in "
                            f"{path}: {owner} on its path holds a list of "
                            f"{len(node)} elements and cannot grow to "
                            f"position {index}: TOML has no null to fill the "
                            "gap with"
                        )
                    )
                child = node[index]
                accessor = index
            elif isinstance(node, dict):
                child = node.get(segment)
                accessor = segment
            else:
                # a scalar on the path is data the library does not own:
                # replacing it silently would destroy it
                expected = "an array" if index is not None else "an object"
                raise UserFacingError(
                    ValueError(
                        f"Cannot store setting {setting_name!r} in "
                        f"{path}: {owner} on its path "
                        f"holds a {type(node).__name__}, not {expected}"
                    )
                )
            if child is None:
                # a plain dict/list converts to the container's own item on
                # the way in, so the walk re-fetches it: writing through the
                # local plain object would land beside the document. A new
                # array of table slots in the document's own tree takes the
                # array-of-tables spelling — the form TOML itself gives a
                # list of tables. A plain document (the file was absent) and
                # a matrix address (the slot itself is an array) keep the
                # plain list: dumps renders the former as rows on its own,
                # and only the inline spelling can hold the latter. An
                # inline table's slot stays inline for the same reason.
                if not wants_array:
                    node[accessor] = {}
                else:
                    slot_is_array = (
                        position + 2 < len(segments) - 1
                        and array_index(segments[position + 2]) is not None
                    )
                    in_own_tree = isinstance(node, (Container, Table))
                    if slot_is_array or not in_own_tree:
                        node[accessor] = []
                    else:
                        node[accessor] = tomlkit.aot()
                        # the first row opens with a blank line when content
                        # already sits beside the array, the way tomlkit
                        # renders a list of tables it converts itself
                        blank_first_row = bool(len(node))
                child = node[accessor]
            node = child
            owner = repr(segment)
        if not isinstance(node, dict):
            # the leaf key always lives in a table
            raise UserFacingError(
                ValueError(
                    f"Cannot store setting {setting_name!r} in "
                    f"{path}: {owner} on its path "
                    f"holds a {type(node).__name__}, not an object"
                )
            )
        return node

    def __remove_leaf(self, segments: List[str], path: Path) -> None:
        """Remove the leaf key, and then the path containers that it leaves empty.

        An emptied array element stays as the empty container that it becomes: an
        array slot cannot hold a marker for "no value" (TOML has no null), and
        keeping the slot keeps the positions of the sibling elements. An array in
        which every element is emptied counts as empty, and it is dropped like an
        emptied table.
        """
        # the walk keeps nodes untyped: the chain pairs every node with its
        # accessor — an array position (``int``) for a list parent, a table
        # key (``str``) otherwise — the walk guarantees the pairing
        chain: List[Tuple[Any, Any]] = []
        node: Any = self.__document_or_load(path)
        for segment in segments[:-1]:
            index = array_index(segment)
            if isinstance(node, list):
                if index is None or index >= len(node):
                    return  # nothing stored under this name
                chain.append((node, index))
                node = node[index]
            elif isinstance(node, dict):
                chain.append((node, segment))
                node = node.get(segment)
            else:
                return  # nothing stored under this name
        if not isinstance(node, dict) or segments[-1] not in node:
            return  # nothing stored under this name
        del node[segments[-1]]
        for parent, accessor in reversed(chain):
            child = parent[accessor]
            if not _emptied_container(child):
                break  # the container still holds data — keep it and those above
            if isinstance(parent, dict):
                del parent[accessor]
            # a list parent keeps the emptied element in its slot: TOML has
            # no null to mark it with, and the siblings keep their positions

    # -- ISettingsSerializer --------------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        path = self.__resolve_file_path(attr is None)
        for key in self.__candidate_keys(setting_name, attr):
            segments = self._setting_segments(key, attr)
            container = self.__read_container(segments, path)
            if container is not None and segments[-1] in container:
                return container[segments[-1]]
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        # the write direction serves the primary address alone: aliases are
        # read addresses, and the primary one outranks them at every load
        key = self.__storage_key(setting_name, attr)
        segments = self._setting_segments(key, attr)
        path = self.__resolve_file_path(attr is None)
        if value is None:
            # TOML has no null: the entry is removed and the next load falls
            # back to the default — the storage contract's rule for a
            # storage without a null form
            self.context.logger.debug(
                "the TOML file %s cannot hold a None value under the key %r; "
                "removing the entry (TOML has no null)",
                path,
                key,
            )
            self.__remove_leaf(segments, path)
            self.__shared_document(path).dirty = True
            return
        # a value with no TOML form (a null nested in a container, text a
        # TOML string cannot hold) raises TypeError here, as a value without
        # a JSON form does in the JSON backend: a single pass's caller hears
        # it, a bulk pass logs and skips it naming the entry
        stored = self.to_toml_value(value)
        container = self.__write_container(key, segments, path)
        leaf = segments[-1]
        held = container.get(leaf)
        if isinstance(held, (dict, list)) and not isinstance(stored, (dict, list)):
            # the container at the leaf is either another member's nested
            # key or data the library does not own: a scalar write over it
            # would destroy it, exactly a scalar on a path would
            raise UserFacingError(
                ValueError(
                    f"Cannot store setting {key!r} in {path}: its key {leaf!r} holds "
                    "a table or an array, and a scalar value would destroy it"
                )
            )
        if (
            held == stored
            # ``True == 1`` in Python: a bool over an int of the same value
            # changes the stored form, it is not the same value already there
            and isinstance(held, bool) == isinstance(stored, bool)
        ):
            # the file already holds the value in its own spelling, and a
            # format-preserving pass leaves that spelling alone: the diff of
            # the pass names only what it actually changed
            return
        if leaf in container:
            # a key shared by two members (or two classes) loses the earlier
            # value at the later write; the channel's lowest-priority record
            # names the overwrite, so a debugging reader is not left guessing
            self.context.logger.debug(
                "the TOML file %s already stores a different value under the key %r; "
                "overwriting it",
                path,
                leaf,
            )
        container[leaf] = stored
        self.__shared_document(path).dirty = True

    def delete(self, setting_name: str, attr: Optional[ISettingAttribute]) -> None:
        path = self.__resolve_file_path(attr is None)
        # an alias left behind would resurrect the value at the next load
        for key in self.__candidate_keys(setting_name, attr):
            self.__remove_leaf(self._setting_segments(key, attr), path)
        self.__shared_document(path).dirty = True

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        path = self.__resolve_file_path(attr is None)
        for key in self.__candidate_keys(setting_name, attr):
            segments = self._setting_segments(key, attr)
            container = self.__read_container(segments, path)
            if container is not None and segments[-1] in container:
                return True
        return False

    def synchronize(self) -> None:
        self.__synchronize_document()

    # -- ISettingNameDescriber -----------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """``key '<address>'``: the address of the member in the document.

        The address joins the placement segments back together with the table
        separator. For a pattern-built name, it is the name itself. A ``path=`` or a
        nested explicit ``name=`` is shown as the dotted address of that place. The
        declared aliases, each of which is a full address of its own, are listed
        next to it. The caller adds the designation of the source next to it, so
        the message names the exact file only once.
        """
        if attr is None:
            return None
        segments = self._setting_segments(self.__storage_key(setting_name, attr), attr)
        return spelled_with_aliases(f"key '{TOML_TABLE_SEPARATOR.join(segments)}'", attr.aliases)

    # -- ISourceDescriber ----------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """``("the TOML file", <path>)``: the document that this backend reads.

        The path is the file of the side that the pass works on: the dynamic file
        for a dynamic entry (``attr=None``), and the file of the static members
        otherwise. The caller lays out the pair. If the address of a member already
        names the file, only the phrase is used, without the path.
        """
        return "the TOML file", str(self.__resolve_file_path(attr is None))

    # -- ISerializerNotificationSink -------------------------------------------

    def on_end_serializer_action(self) -> None:
        # the pass brackets closed: release the shared document. The last
        # holder out drops the registry entry, so the next pass re-reads
        # the file — external edits included
        entry = self.__shared
        if entry is None:
            return
        self.__shared = None
        with _FILE_LOCK:
            entry.users -= 1
            if entry.users == 0 and _SHARED_DOCUMENTS.get(entry.path) is entry:
                del _SHARED_DOCUMENTS[entry.path]

    # -- IDynamicSettingsInfo ---------------------------------------------------

    def get_dynamic_settings_names(self) -> List[str]:
        """Full names of the dynamic entries of the bound settings class.

        The section layout holds one table per settings class, and this serializer
        returns the entries of its own class. In a flat layout, it picks the full
        names of the class out of the document root. The entries of other classes
        are handled by their own serializers: every pass is bound to one class, and
        the plugin filters what it reads down to its class anyway.

        The enumeration walks the stock section. An override of
        :meth:`_setting_segments` that relocates dynamic entries must move the
        enumeration in step, or :meth:`load_settings` will not find the entries
        again.
        """
        settings_class = self.context.settings_class
        path = self.__resolve_file_path(True)
        pattern = self.__dynamic_name_pattern()
        delimiter = self.delimiter()
        class_key = get_dynamic_settings_class_prefix(settings_class, self, pattern)[
            : -len(delimiter)
        ]
        return dynamic_settings_names(
            self.__document_or_load(path),
            settings_class=settings_class,
            serializer=self,
            pattern=pattern,
            section=self.__dynamic_section_segments(),
            class_key=class_key,
            # the class part nests like every key: the section table holds
            # the first level, the class's table sits at the end of the chain
            class_location=toml_table_levels(class_key),
            path=path,
        )
