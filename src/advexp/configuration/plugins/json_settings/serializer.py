# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The serializer of the JSON file configuration source.

The file is one JSON object from which the source reads members. The keys
are full setting names (the explicit ``name=`` or the name pattern of the
link, which is the full ``{module}.{class}.{member}`` pattern by default),
and the values are native JSON.

The link that the class's chain carries configures the source. Its
``file=`` names the file that the link reads, and its ``path=`` anchors
every key of the link inside a subtree of the document. The ``path=`` of a
member locates the key within that subtree, and the path of the link is
added in front of it: ``json_source(file="app.json", path="/env/prod")``
reads members with ``path="/server"`` from ``["env"]["prod"]["server"]``. A
member that must live outside the subtree of the link needs a link of its
own: the same file under another ``path=``.

The optional ``path=`` of
:class:`~advexp.configuration.plugins.json_settings.setting.JSONSetting`
locates a key in the document tree as a JSON Pointer (RFC 6901): a leading
``/``, then slash-separated segments, with ``~1``/``~0`` escaping.
``JSONSetting(name="host", path="/net/proxy")`` reads the key from
``{"net": {"proxy": {...}}}``, and ``path="/mirrors/1"`` reads it from the
second element of the ``mirrors`` array. A segment that consists only of
digits indexes an array if the node it steps into is an array, and names an
object key otherwise.

Declared ``aliases=`` widen the read. Every alias is a full key of its own.
A load looks up the primary key first, then the aliases in their order
(each one placed by the same ``path=``), and the first key found wins.

The dynamic side reads the group of a writer. A class that declares the
group key of the writing class (``json_source(dynamic_of=...)``) reads the
dynamic entries that this class stored. The group is placed by the section
parameters of the writing side, in the file of the link by default or in a
``dynamic_file=`` of its own. The entries are read through the read-only
dynamic plugin of ``advexp.configuration.plugins.json_dynamic_settings``.

A pass reads the document once and shares it with every serializer over
that file. For example, a configuration chain can mix attribute classes
(the stock ``JSONSetting`` and a registered subclass, say); all of them then
read one consistent document instead of two private views. The shared entry
lives only inside the pass brackets, so a later pass re-reads the file,
including any external edits. Keys that the source does not know are
ignored and left as they are: the file belongs to whoever writes it, and
this package only reads it.

The source is read-only: it responds to ``load`` and ``contains``. The
write operations of the serializer contract refuse with an error (a
``UserFacingError`` around a ``NotImplementedError`` that names the
source), and the facade of the package never calls them.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from advexp.configuration.plugin_api import (
    NOT_FOUND,
    PACKAGE_NAME,
    DocumentDynamicSettingsPlugin,
    IDynamicSettingsInfo,
    ISettingAttribute,
    SettingsBaseSerializer,
    UserFacingError,
)
from advexp.configuration.plugins.json_settings.dynamic_configuration import (
    JSONDynamicSettingsConfiguration,
)
from advexp.configuration.plugins.json_settings.setting import JSONSetting
from advexp.settings_base.dynamic_document import (
    JSON_DYNAMIC_GROUP_METADATA,
    document_dynamic_plugin,
    dynamic_reader_entry_segments,
    dynamic_reader_names,
    dynamic_section_segments,
    dynamic_writer_group,
    resolve_dynamic_document_file,
)
from advexp.settings_base.env_parameter import EnvParameter, resolve_templated_path
from advexp.settings_base.file_bom import UTF8_BOM
from advexp.settings_base.json_file import (
    JSON_DYNAMIC_FILE_METADATA,
    JSON_FILE_METADATA,
)
from advexp.settings_base.names import (
    DEFAULT_SETTINGS_NAME_PATTERN,
    get_full_setting_name,
    setting_name_candidates,
    spelled_with_aliases,
)
from advexp.settings_base.pointer import array_index, pointer_steps
from advexp.settings_base.source_link import SourceLink
from advexp.settings_base.source_link_sink_interface import ISourceLinkSink
from advexp.settings_base.sources import (
    LINK_FILE_PARAM,
    LINK_NAME_PATTERN_PARAM,
    LINK_PARAMETERS_PARAM,
    LINK_PATH_PARAM,
    SOURCE_CHAIN_METADATA,
    Sources,
)

_FILE_LOCK = threading.RLock()
"""Serializes file reads and the shared-document registry of concurrently
running passes."""

_SHARED_DOCUMENTS: Dict[Path, "_SharedDocument"] = {}
"""The in-memory document of each file in active use, keyed by the file
path (guarded by ``_FILE_LOCK``)."""


class _SharedDocument:
    """The document of one configuration file, shared by the serializers that
    read it.

    ``users`` counts the serializers that have joined. The entry stays in the
    registry while at least one of them is inside its pass brackets, and the
    last one to leave removes it. The next pass then re-reads the file.
    """

    __slots__ = ("path", "document", "users")

    def __init__(self, path: Path, document: Dict[str, Any]) -> None:
        self.path = path
        self.document = document
        self.users = 0


class JSONSettingsSerializer(SettingsBaseSerializer, ISourceLinkSink, IDynamicSettingsInfo):
    """Loads configuration from a JSON file keyed by full setting names.

    The ``path=`` of the link anchors the keys of the link inside a subtree of
    the document. The ``path=`` on the attribute locates the key within that
    subtree as a JSON Pointer. A path segment that consists only of digits
    indexes an array if the node it steps into is an array, and names an object
    key otherwise. The name itself is a plain key and may contain any
    characters.

    The dynamic side reads the group of a writer: the entries that the writing
    class stored, addressed by the group key that the class declared. The
    placement of every key is built by the :meth:`_setting_segments` hook,
    which is the placement extension point of the source.
    """

    def __init__(self) -> None:
        super().__init__()
        # name-mangled: the pass state dispatched through self, kept out
        # of a subclass's reach
        self.__shared: Optional[_SharedDocument] = None
        self.__file: Optional[Union[str, os.PathLike]] = None
        self.__path: Optional[str] = None
        self.__name_pattern: Optional[str] = None
        self.__parameters: Optional[Tuple[EnvParameter, ...]] = None

    # -- ISourceLinkSink --------------------------------------------------------

    def set_source_link(self, link: SourceLink) -> None:
        """``ISourceLinkSink`` delivery: the link that this source reads.

        The ``file=`` of the link names the file, its ``path=`` anchors the keys of
        the link inside a subtree of the document, and its ``name_pattern=`` sets
        the pattern that builds the keys. Its ``parameters=`` carries the path
        parameters through which a templated ``file=`` is resolved. The link is the
        only configuration of this source: a layered class declares no module
        default and no per-class file binding.
        """
        self.__file = link.param(LINK_FILE_PARAM)
        self.__path = link.param(LINK_PATH_PARAM)
        self.__name_pattern = link.param(LINK_NAME_PATTERN_PARAM)
        self.__parameters = link.param(LINK_PARAMETERS_PARAM)

    # -- document handling ---------------------------------------------------

    def __resolve_file_path(self) -> Path:
        """The file of the link that this serializer serves.

        The path is absolute and is anchored on the configuration class. The first
        access of the class anchors the exact file, and every pass during the life
        of the class (the documents it reads, the diagnostics it quotes) keeps
        using that file, even if the working directory changes. The anchor is kept
        per resolved link file: two links of one chain that read two files keep
        separate anchors, and a templated link anchors the file of each environment
        under the file that it resolved to. As a result, a switched variable
        re-anchors, instead of moving a single anchor back and forth between
        environments.
        """
        configured = self.__file
        if configured is None:
            raise UserFacingError(
                ValueError(
                    "the JSON file source has no file to read: the link was built "
                    f"without one (json_source(file=...) spells it, {PACKAGE_NAME})"
                )
            )
        resolved = resolve_templated_path(
            self.context,
            configured,
            self.__parameters,
            f"the JSON file source ({PACKAGE_NAME})",
        )
        return self.context.anchored_file_path((JSON_FILE_METADATA, resolved), resolved)

    def __load_document(self, path: Path) -> Dict[str, Any]:
        """The parsed document of the file; an absent file gives an empty document.

        Both empty outcomes write a debug record. The "miss" message of the pass
        cannot distinguish an absent file, an empty document, and a document that
        does not contain the key, and a reader who debugs an empty load needs these
        cases to be told apart.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.context.logger.debug("the JSON file %s does not exist, treating it as empty", path)
            return {}
        except OSError as exc:
            # an unreadable-but-present file (permissions, a non-directory on
            # the path) must reach the user: silently falling back to an
            # empty document would mask the configuration
            raise UserFacingError(exc) from exc
        except UnicodeError as exc:
            # an undecodable file (a UTF-16 one, say) must reach the user
            # the same way; the bare codec message names neither the
            # library, the file nor the pass, so the wrapper carries the
            # phrase
            raise UserFacingError(
                ValueError(f"{PACKAGE_NAME}: cannot read the JSON configuration file {path}: {exc}")
            ) from exc
        if text.startswith(UTF8_BOM):
            # the storing side of the family keeps a file's BOM through
            # its saves, so the reading side tolerates one too
            text = text[len(UTF8_BOM) :]
        try:
            document = json.loads(text)
        except ValueError as exc:
            # a corrupt configuration file must reach the user, not fall
            # back to defaults silently; the package name names the
            # library as the source, the path names the file, and "JSON
            # configuration file" names the pass that read it — the bare
            # parser message names none of the three
            raise UserFacingError(
                ValueError(
                    f"{PACKAGE_NAME}: cannot parse the JSON configuration file {path}: {exc}"
                )
            ) from exc
        if not isinstance(document, dict):
            raise UserFacingError(
                ValueError(
                    f"JSON configuration file {path} must contain an object at the top level, "
                    f"got {type(document).__name__}"
                )
            )
        if not document:
            self.context.logger.debug("the JSON file %s contains no keys", path)
        return document

    def __document_or_load(self, path: Path) -> Dict[str, Any]:
        """The shared document entry of this file; the serializer joins it on first
        access.

        The first access over a file loads it into the registry. Every further
        serializer over the same file (for example, the attribute-class
        serializers of one mixed configuration class, or a concurrent pass) joins
        that entry, so all of them read one document. A join holds the entry until
        ``on_end_serializer_action`` releases it. A bracket works on one file, so a
        single joined slot is enough.
        """
        entry = self.__shared
        if entry is None:
            with _FILE_LOCK:
                entry = _SHARED_DOCUMENTS.get(path)
                if entry is None:
                    entry = _SharedDocument(path, self.__load_document(path))
                    _SHARED_DOCUMENTS[path] = entry
                entry.users += 1
                self.__shared = entry
        return entry.document

    # -- the dynamic side ----------------------------------------------------

    def __dynamic_plugin(self) -> Optional[DocumentDynamicSettingsPlugin]:
        """The dynamic plugin pinned to this source; ``None`` when the dynamic
        package is not imported.

        The lookup goes through the context, using the pin built from the
        attribute class of this source. The plugin package imports this module for
        its binding, so importing the plugin class here would be circular.
        """
        return document_dynamic_plugin(self.context, JSONSetting)

    def __writer_group(self) -> Optional[str]:
        """The group key of the writing class; ``None`` when the class declared none
        (the source then reads no dynamic entries).
        """
        return dynamic_writer_group(self.context, JSON_DYNAMIC_GROUP_METADATA)

    def __family_link(self) -> Optional[SourceLink]:
        """The link of the JSON family in the class's chain; ``None`` when unbound.

        The dynamic pass reads the link from the chain itself, not from the
        ``ISourceLinkSink`` delivery. That delivery serves the instances of the
        pipeline, while the dynamic plugin drives its own serializer over the
        class. It is the same chain link either way, reached here without the
        delivery.
        """
        chain: Any = self.context.get_class_metadata(SOURCE_CHAIN_METADATA)
        if not isinstance(chain, Sources):
            return None
        for link in chain:
            if link.attribute_class is JSONSetting:
                return link
        return None

    def __resolve_dynamic_file_path(self) -> Path:
        """The file of the dynamic pass: the file that holds the group of the writer.

        The levels mirror those of the writing side, and the default is the shared
        document. The levels are: the ``dynamic_file=`` binding of the class, the
        declaration of the module, the module-wide value of the holder and, when
        none of these own levels is set, the ``file=`` of the family link. The path
        is anchored on the configuration class like the static one, under the own
        anchor key of the dynamic side.
        """
        link = self.__family_link()

        def link_file() -> Optional[Union[str, os.PathLike]]:
            return link.param(LINK_FILE_PARAM) if link is not None else None

        configured = resolve_dynamic_document_file(
            self.context,
            dynamic_file_metadata=JSON_DYNAMIC_FILE_METADATA,
            module_default_holder=JSONDynamicSettingsConfiguration,
            static_levels=link_file,
        )
        if configured is None:
            # configuration errors must reach the user: silently reading an
            # empty document would mask them
            raise UserFacingError(
                ValueError(
                    "JSON configuration file for dynamic settings is not "
                    "configured: give the dynamic entries a file of their own "
                    "(json_source(dynamic_file=...), "
                    "JSONDynamicSettingsConfiguration.file_path or a "
                    "for_this_module declaration) or bind the class's source "
                    f"to a file (json_source(file=...)) ({PACKAGE_NAME})"
                )
            )
        parameters = link.param(LINK_PARAMETERS_PARAM) if link is not None else None
        resolved = resolve_templated_path(
            self.context,
            configured,
            parameters,
            f"the JSON file source ({PACKAGE_NAME})",
        )
        return self.context.anchored_file_path((JSON_DYNAMIC_FILE_METADATA, resolved), resolved)

    # -- name paths ----------------------------------------------------------

    def __static_key(self, setting_name: str, attr: ISettingAttribute) -> str:
        """The document key that the pass addresses for the member.

        An explicit ``name=`` is the full address in the document, exactly as
        delivered. The key of every other member is built from the name pattern of
        the link (the full pattern if the link sets none) by the shared name
        builder, so the name wishes of the serializer apply to these keys in the
        same way as to the default spelling.
        """
        if attr.name:
            return setting_name
        member_name = attr.bound_name
        if not member_name:
            raise ValueError(
                "the JSON file source requires either an explicit name= or a member "
                "name to build the document key"
            )
        return get_full_setting_name(
            member_name,
            attr,
            self.context.settings_class,
            self,
            pattern=self.__name_pattern or DEFAULT_SETTINGS_NAME_PATTERN,
        )

    def __candidate_keys(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Tuple[str, ...]:
        """The keys that a lookup walks: the primary key, then the declared aliases in
        their order. Every alias is a full key of its own.
        """
        if attr is None:
            return (setting_name,)
        return setting_name_candidates(self.__static_key(setting_name, attr), attr)

    def _setting_segments(self, setting_name: str, attr: Optional[ISettingAttribute]) -> List[str]:
        """Location segments of an entry in the document: the placement hook.

        Every read (``load``, ``contains``) locates its key through this method.
        This makes it the placement extension point of the source: a protected hook
        of the inheritance contract, which subclasses override (calling ``super()``
        to get the stock placement) to relocate keys at runtime.

        A dynamic entry (``attr is None``) is routed to the group of the writer that
        the class declared. Its location is the layout of the writer, read as laid
        out. A class that declared no group has no dynamic entries to place. The
        location of a declared member consists of the ``path=`` subtree of the link
        first (the link anchors every key that it serves inside it), then the
        ``path=`` of the attribute within that subtree, and the name key last.
        """
        if attr is None:
            group = self.__writer_group()
            if group is None:
                raise ValueError(
                    "the JSON file source serves only declared members. A "
                    "dynamic entry requires the group key of the writing class "
                    "(json_source(dynamic_of=...))"
                )
            return dynamic_reader_entry_segments(
                self.context,
                self.__dynamic_plugin(),
                self,
                setting_name,
                group,
                [group],
                self.__resolve_dynamic_file_path(),
            )
        segments: List[str] = []
        if self.__path is not None:
            segments += pointer_steps(self.__path)
        setting = self.attribute_of(attr, JSONSetting)
        path = setting.path if setting is not None else None
        if path is not None:
            segments += pointer_steps(path)
        segments.append(setting_name)
        return segments

    def __read_container(self, segments: List[str], path: Path) -> Optional[Dict[str, Any]]:
        """The object that holds the leaf key, or ``None`` where the path breaks off.

        A segment that consists only of digits reads an array position if the node
        it steps into is a list, and an object key otherwise. The path breaks off
        at a missing key, an out-of-range position, or a scalar in the middle of
        the path.
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

    # -- ISettingsSerializer --------------------------------------------------

    def load(self, setting_name: str, attr: Optional[ISettingAttribute]) -> Any:
        path = (
            self.__resolve_file_path() if attr is not None else self.__resolve_dynamic_file_path()
        )
        for key in self.__candidate_keys(setting_name, attr):
            segments = self._setting_segments(key, attr)
            container = self.__read_container(segments, path)
            if container is not None and segments[-1] in container:
                return container[segments[-1]]
        return NOT_FOUND

    def save(self, setting_name: str, attr: Optional[ISettingAttribute], value: Any) -> None:
        """Refused with an error: a read-only source never writes.

        The facade of the package never calls this operation, so a caller that
        reaches it has mistaken the source for a storage backend. The refusal says
        so, instead of a silent no-op that would hide the bug.
        """
        raise UserFacingError(
            NotImplementedError(
                f"the JSON file source is read-only: it loads and never writes ({PACKAGE_NAME})"
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
                f"the JSON file source is read-only: it loads and never deletes ({PACKAGE_NAME})"
            )
        )

    def contains(self, setting_name: str, attr: Optional[ISettingAttribute]) -> bool:
        path = (
            self.__resolve_file_path() if attr is not None else self.__resolve_dynamic_file_path()
        )
        for key in self.__candidate_keys(setting_name, attr):
            segments = self._setting_segments(key, attr)
            container = self.__read_container(segments, path)
            if container is not None and segments[-1] in container:
                return True
        return False

    # -- ISettingNameDescriber ----------------------------------------------

    def describe_setting_name(
        self, setting_name: str, attr: Optional[ISettingAttribute]
    ) -> Optional[str]:
        """``key '<name>'``: the key of the member in the document, with the declared
        aliases listed next to the primary one.

        The caller adds the designation of the source next to it, so the message
        names the exact file only once.
        """
        if attr is None:
            return None
        segments = self._setting_segments(self.__candidate_keys(setting_name, attr)[0], attr)
        return spelled_with_aliases(f"key '{segments[-1]}'", attr.aliases)

    # -- ISourceDescriber ----------------------------------------------

    def describe_source(
        self, attr: Optional[ISettingAttribute]
    ) -> Optional[Tuple[str, Optional[str]]]:
        """``("the JSON file", <path>)``: the document that this source reads.

        The path is the file of the side that the pass works on: the dynamic file
        for a dynamic entry (``attr=None``), and the file of the declared members
        otherwise. The caller lays out the pair. If the address of a member already
        names the file, the phrase is used alone.
        """
        if attr is None:
            return "the JSON file", str(self.__resolve_dynamic_file_path())
        return "the JSON file", str(self.__resolve_file_path())

    # -- ISerializerNotificationSink -------------------------------------------

    def on_end_serializer_action(self) -> None:
        # the pass brackets closed: release the shared document. The last
        # holder out drops the registry entry, so the next pass re-reads
        # the file, external edits included
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
        """Full names of the entries of the writer's group that this source reads.

        The names carry the key of the writer (the ``D`` marker with the address of
        the group) and serve the collection of the reading plugin. A class that
        declared no group reads none. The section and the place of the group in it
        are the layout of the writer, read as laid out.
        """
        group = self.__writer_group()
        if group is None:
            return []
        path = self.__resolve_dynamic_file_path()
        return dynamic_reader_names(
            self.__document_or_load(path),
            serializer=self,
            class_key=group,
            section=dynamic_section_segments(self.context, self.__dynamic_plugin()),
            # the writer's class part is one object key of its own
            class_location=[group],
            path=path,
        )
