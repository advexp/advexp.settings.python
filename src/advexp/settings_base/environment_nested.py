# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Nested addressing of object members through the environment namespace.

A member annotated with a dataclass is one *nested object*. If the
``nested_delimiter`` option of the family is set, the environment addresses
the fields of the object through the delimiter: ``APP_DB__PORT`` is the
``port`` field of the ``db`` member, and ``APP_DB__DEEP__V4`` is the ``v4``
field of ``db.deep``. An address consists of the variable name of the
member, the delimiter, and the field name with its case applied, to any
depth. The addressing is one more naming rule of the namespace, so it lives
next to the options: every backend of the family resolves a variable in the
same way, whether it is a settings backend or a read-only configuration
source.

Three layers meet at one nested object, and each layer wins over the one
before it:

* The declared default of the member, which is the merge base. Fields that
  the environment leaves unset keep the values of the declared default
  instance. A variable that changes a single field therefore updates the
  object and leaves the rest as declared (a *partial update*).
* The whole-object form: a variable that holds a JSON object, at the own
  name of the member and at the own name of any nested object
  (``APP_DB__DEEP`` holds the whole ``deep`` object).
* The per-field variables: the delimiter addresses of the leaves.

Saving mirrors the addressing: each field is written to its own variable,
and the whole-object variables are removed. Only one reading form remains,
and a saved object loads back as it was saved. Deleting removes the variable
of the member together with every nested address, and a containment check is
satisfied by any of them.

Under ``name_case=NameCase.ANY``, every address (the one of the member and
the nested ones) is looked up in any spelling, and a write touches the
spelling that it found
(:func:`advexp.settings_base.environment_lookup.environment_key`).
"""

from __future__ import annotations

import dataclasses
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterator,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
)

from advexp.settings_base.conversion import (
    _dataclass_field_types,
    _dataclass_fields,
    _json_decode_if_possible,
    to_json_value,
    unwrap_annotation,
)
from advexp.settings_base.environment_lookup import environment_key
from advexp.settings_base.environment_options import (
    NESTED_DELIMITER,
    apply_environment_case,
)
from advexp.settings_base.member_load_error import MemberLoadError
from advexp.settings_base.not_found import NOT_FOUND
from advexp.settings_base.setting_attribute_interface import ISettingAttribute
from advexp.settings_base.setting_member import SettingMember
from advexp.settings_base.settings_meta import SettingsMeta


def _stored_key(
    environ: Mapping[str, str],
    name: str,
    options: Mapping[str, Any],
    source: str,
) -> str:
    """The key a write or a drop touches: the spelling found in the
    namespace, or the built name when no spelling is there."""
    key = environment_key(environ, name, options, source)
    return name if key is None else key


def nested_member(
    attr: Optional[ISettingAttribute], settings_class: SettingsMeta
) -> Optional[SettingMember]:
    """Return the registry entry behind ``attr`` when it is bound to a member.

    Nested addressing needs what the attribute contract does not carry: the
    annotation of the member and its declared default. Both are stored in the
    members registry of the reading class, keyed by the bound name of the
    attribute. A dynamic entry that has no attribute, or an attribute of a
    foreign class, returns ``None``, and the backend stays on flat addressing.
    """
    bound = None if attr is None else attr.bound_name
    if bound is None:
        return None
    members: Dict[str, SettingMember] = settings_class.__settings_members__
    return members.get(bound)


def nested_object_type(annotation: Any) -> Optional[type]:
    """Return the dataclass of a nested-object annotation; ``None`` for anything
    else.

    The ``Optional`` and ``Annotated`` wrappers are unwrapped: ``Optional[Db]``
    is a nested object in the same way as ``Db``.
    """
    unwrapped = unwrap_annotation(annotation)
    if isinstance(unwrapped, type) and dataclasses.is_dataclass(unwrapped):
        return unwrapped
    return None


def nested_delimiter_of(options: Optional[Mapping[str, Any]]) -> Optional[str]:
    """The family's nested delimiter of a stored options entry, when set."""
    if not options:
        return None
    delimiter = options.get(NESTED_DELIMITER)
    return delimiter if isinstance(delimiter, str) and delimiter else None


def _nested_nodes(
    node_type: type,
    node_name: str,
    path: Tuple[str, ...],
    seen: FrozenSet[type],
    options: Mapping[str, Any],
    delimiter: str,
) -> Iterator[Tuple[str, Tuple[str, ...], bool]]:
    field_types = _dataclass_field_types(node_type)
    for field in _dataclass_fields(node_type):
        if not field.init:
            # a field the constructor refuses cannot be restored; its
            # address would promise a round trip it cannot keep
            continue
        name = node_name + delimiter + apply_environment_case(field.name, options)
        child_path = path + (field.name,)
        child_type = nested_object_type(field_types.get(field.name))
        if child_type is not None and child_type not in seen:
            yield name, child_path, False
            yield from _nested_nodes(
                child_type, name, child_path, seen | {child_type}, options, delimiter
            )
        else:
            # a leaf — a repeating class included: its whole-object form
            # is the only finite address it has
            yield name, child_path, True


def _nested_environment_nodes(
    env_name: str, member: SettingMember, options: Mapping[str, Any]
) -> Iterator[Tuple[str, Tuple[str, ...], bool]]:
    """Yield every nested address below the own variable of one member.

    It yields ``(variable name, field path, leaf)`` depth first. The own
    variable of a nested object (its whole-object form) is yielded first, and
    then the function descends into the object. The variable of a plain field is
    yielded once. The own variable of the member is not included, because the
    callers already hold it. Nothing is yielded if the member is not a nested
    object or if the delimiter of the family is off.
    """
    delimiter = nested_delimiter_of(options)
    root = nested_object_type(member.annotation)
    if delimiter is None or root is None:
        return
    yield from _nested_nodes(root, env_name, (), frozenset({root}), options, delimiter)


def _collect_node(
    node_type: type,
    node_name: str,
    seen: FrozenSet[type],
    options: Mapping[str, Any],
    delimiter: str,
    environ: Mapping[str, str],
    source: str,
) -> Any:
    """Return the environment layer at one nested object; ``None`` when nothing is
    set.

    A whole-object variable at the own name of the node is decoded as a JSON
    object, and it opens the layer. The variable of each field is then applied on
    top of it: the per-field spelling wins over the whole-object one, node by
    node. A whole-object variable that holds something other than a JSON object
    is returned as it is. It cannot be merged with the fields, so the ordinary
    conversion is left to report it.
    """
    layer: Dict[str, Any] = {}
    whole_key = environment_key(environ, node_name, options, source)
    whole = environ[whole_key] if whole_key is not None else None
    if whole is not None:
        decoded = _json_decode_if_possible(whole)
        if isinstance(decoded, dict):
            layer.update(decoded)
        else:
            return decoded
    field_types = _dataclass_field_types(node_type)
    for field in _dataclass_fields(node_type):
        if not field.init:
            continue
        name = node_name + delimiter + apply_environment_case(field.name, options)
        child_type = nested_object_type(field_types.get(field.name))
        if child_type is not None and child_type not in seen:
            child = _collect_node(
                child_type, name, seen | {child_type}, options, delimiter, environ, source
            )
            if child is not None:
                layer[field.name] = _merge_node(layer.get(field.name), child)
        else:
            key = environment_key(environ, name, options, source)
            value = environ[key] if key is not None else None
            if value is not None:
                layer[field.name] = value
    return layer or None


def _merge_node(whole_form: Any, nested: Any) -> Any:
    if isinstance(whole_form, dict) and isinstance(nested, dict):
        return _deep_merge(whole_form, nested)
    return nested


def _default_layer(member: SettingMember) -> Dict[str, Any]:
    """Return the declared default of the member as the merge base of a partial
    load.

    A required member has no default to merge onto, and neither has a member
    without a declared default. In both cases the base is empty, so the object
    is built from the environment layer alone, and the own field defaults of the
    dataclass fill in what stays unset.
    """
    try:
        default = member.descriptor.resolved_default()
    except MemberLoadError:
        return {}
    rendered = to_json_value(default) if default is not None else None
    return rendered if isinstance(rendered, dict) else {}


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def load_nested_environment_value(
    env_name: str,
    member: SettingMember,
    options: Mapping[str, Any],
    environ: Mapping[str, str],
    source: str,
) -> Any:
    """Return the nested-aware raw value of one member for the load pipeline.

    The result is :data:`~advexp.settings_base.not_found.NOT_FOUND` if neither
    the own variable of the member nor any nested address holds a value.
    Otherwise, the environment layer (the whole-object form under the per-field
    variables) is merged on top of the rendering of the declared default. Fields
    that the environment leaves unset therefore keep the values of the declared
    instance: this is a partial update.

    If the own variable of the member holds a payload that is not an object, it
    is returned untouched. The whole-object form is broken in this case, and the
    ordinary conversion reports it in the flat way.

    A member outside the nested addressing (no delimiter, or no dataclass
    annotation) reads only its own variable. ``source`` is the human-readable
    label of the namespace, used in the error that a lookup conflict raises.
    """
    delimiter = nested_delimiter_of(options)
    root = nested_object_type(member.annotation)
    if delimiter is None or root is None:
        key = environment_key(environ, env_name, options, source)
        value = environ[key] if key is not None else None
        return NOT_FOUND if value is None else value
    collected = _collect_node(
        root, env_name, frozenset({root}), options, delimiter, environ, source
    )
    if collected is None:
        return NOT_FOUND
    if not isinstance(collected, dict):
        return collected
    base = _default_layer(member)
    return _deep_merge(base, collected) if base else collected


def contains_nested_environment_value(
    env_name: str,
    member: SettingMember,
    options: Mapping[str, Any],
    environ: Mapping[str, str],
    source: str,
) -> bool:
    """Whether any address of the member — its own or a nested one — is set."""
    if environment_key(environ, env_name, options, source) is not None:
        return True
    return any(
        environment_key(environ, name, options, source) is not None
        for name, _path, _leaf in _nested_environment_nodes(env_name, member, options)
    )


def delete_nested_environment_values(
    env_name: str,
    member: SettingMember,
    options: Mapping[str, Any],
    environ: MutableMapping[str, str],
    source: str,
) -> None:
    """Remove every address of the member: its own variable and the nested ones.

    A leftover nested address would bring its field back on the next load, so
    deleting the member clears the whole subtree. Each address is removed under
    the spelling in which the namespace holds it.
    """
    names = [env_name]
    names.extend(
        name for name, _path, _leaf in _nested_environment_nodes(env_name, member, options)
    )
    for name in names:
        environ.pop(_stored_key(environ, name, options, source), None)


def _nested_field_value(value: Any, path: Tuple[str, ...]) -> Any:
    """Return the field of ``value`` at ``path``; ``None`` when the chain breaks.

    Saving walks the declared field paths over the live value. If the value does
    not carry the chain (for example, an instance that has drifted from the
    annotation), the field is read as unset, and the pass does not fail.
    """
    for name in path:
        value = getattr(value, name, None)
    return value


def save_nested_environment_values(
    env_name: str,
    member: SettingMember,
    options: Mapping[str, Any],
    environ: MutableMapping[str, str],
    source: str,
    value: Any,
    render: Callable[[Any], str],
) -> None:
    """Store one member field by field, each field in its own variable.

    The value of a field is written to its variable in the form that ``render``
    produces. This is the own value form of the backend, so its overrides apply.
    A field whose value is ``None`` unsets its variable (the environment has no
    null form). The whole-object variables (the own variable of the member and
    those of the nested objects) are removed, so only one reading form remains.

    If a value turns out not to be the nested object after all, the flat
    spelling is kept: the value is rendered whole into the own variable of the
    member, and the nested addresses are dropped.

    Under :attr:`~advexp.settings_base.name_case.NameCase.ANY`, every write and
    every removal touches the spelling that the namespace already holds. An
    address that has no spelling is written under its built name.
    """
    if value is not None and not (dataclasses.is_dataclass(value) and not isinstance(value, type)):
        for name, _path, _leaf in _nested_environment_nodes(env_name, member, options):
            environ.pop(_stored_key(environ, name, options, source), None)
        environ[_stored_key(environ, env_name, options, source)] = render(value)
        return
    environ.pop(_stored_key(environ, env_name, options, source), None)
    for name, path, leaf in _nested_environment_nodes(env_name, member, options):
        if not leaf:
            environ.pop(_stored_key(environ, name, options, source), None)
            continue
        field_value = _nested_field_value(value, path)
        if field_value is None:
            environ.pop(_stored_key(environ, name, options, source), None)
        else:
            environ[_stored_key(environ, name, options, source)] = render(field_value)
