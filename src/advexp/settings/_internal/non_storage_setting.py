# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The core's member without a storage."""

from typing import Any, Callable, Mapping, Optional

from advexp.settings._internal.non_storage_serializer import NonStorageSerializer
from advexp.settings._internal.settings_attribute import SettingsAttribute
from advexp.settings_base.library_configuration import LibraryConfiguration
from advexp.settings_base.no_default import NO_DEFAULT
from advexp.settings_base.required import REQUIRED


class NonStorageSetting(SettingsAttribute):
    """The member without a storage.

    Served by
    :class:`~advexp.settings._internal.non_storage_serializer.NonStorageSerializer`:
    no storage is ever asked for the member. Its value is the declared default
    or the last assignment, and the load pass resets it to the declared
    default. Save and delete skip the member, while ``update_from_dict`` and
    ``update_from_object`` set it like any other member, and ``to_dict``
    includes it.
    """


def non_storage_setting(
    *,
    name: Optional[str] = None,
    default: Any = NO_DEFAULT,
    metadata: Optional[Mapping[str, Any]] = None,
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
    """Declare a member without a storage. This is the type-checker-friendly
    spelling.

    This is the own declaration of the core: a member that no storage ever
    serves. Its value is the declared default or the last assignment, and the
    load pass resets it to the declared default. Save and delete skip it, while
    ``update_from_dict`` and ``update_from_object`` set it like any other
    member, and ``to_dict`` includes it. A plain function that returns ``Any``
    is the spelling that mypy accepts; the factories of the individual backends
    (``json_setting`` and the like) use the same form.

    ``default=`` is required: a member that no storage ever serves must state
    its value, and the factory refuses a declaration without one.

    The keyword parameters after ``metadata`` are the declared value
    constraints. ``gt/ge/lt/le/eq/ne`` compare the value, ``min_length`` and
    ``max_length`` bound ``len(value)``, ``regex`` is an unanchored pattern
    that a ``str`` value must match, and ``validator`` is a callable that
    receives the value and returns whether it passes. They apply wherever a
    value reaches the member: declared defaults, assignment, load,
    ``update_from_dict`` and ``update_from_object``, and save.

    A comparison parameter also accepts the attribute object of a member that
    was declared earlier in the same class body. This is a member reference
    (``ge=min_port``). It is compared with the current value of that member
    wherever the whole class is checked at once (class creation, load, update,
    save, :meth:`~advexp.settings.Settings.validate_settings`). ``when=`` takes
    only such a reference: while the referenced member is falsy, none of the
    constraints of this member apply. Rules that a comparison cannot state
    (for example, conditional requirements or "at least one of") belong to the
    ``__validate__`` hook of the settings class.
    """
    if default is NO_DEFAULT or default is REQUIRED:
        raise TypeError(
            "non_storage_setting() declares a member that no storage ever serves, so it "
            "needs a value: pass default="
        )
    return NonStorageSetting(
        name=name,
        default=default,
        metadata=metadata,
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


# the member without a storage is served by the no-op serializer: importing
# this module (the facade's ``non_storage_setting`` factory) enables that pair
LibraryConfiguration.register_settings_attribute(NonStorageSetting, NonStorageSerializer)
