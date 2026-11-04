"""Validation at the class statement: the declaration itself is checked.

Creating a settings class validates the declared state:

- Every ``default=`` is checked against the constraints of the member. A
  ``NO_DEFAULT`` member serves ``None`` and must accept it.
- The declaration parameters are checked against each other: a validator
  that is not callable, ordering bounds that are mixed with string bounds,
  and a pattern that does not compile.
- Member references are checked against the class that declares them.

The classes of this category exist to fail their own creation, so they are
declared inside the tests. A ``class`` statement at the module level that
raises would break the import of the whole suite.

One scenario cannot be covered here by construction, and it lives only in
the parametrized suites: a cycle of member references. It cannot be written
with plain declarations, because a bound must exist before the attribute
that references it. The original suite therefore probes the cycle detector
through the internals of the library.
"""

import pytest

from advexp.settings import Settings, non_storage_setting
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.json_settings import json_setting


def test_bad_default_fails_the_class_statement():
    """A declared default is checked against the member's own bounds."""
    with pytest.raises(TypeError) as info:

        class BadDefaultSettings(Settings):
            port: int = json_setting(name="port", default=70000, le=65535)

    assert str(info.value) == (
        "invalid defaults in BadDefaultSettings:\n"
        "  - port: value 70000 must be less than or equal to 65535"
    )


def test_no_default_member_rejected_by_eq_fails_the_class_statement():
    """A NO_DEFAULT member serves None, and None does not pass eq: the
    member has no valid state, and the statement says so."""
    with pytest.raises(TypeError) as info:

        class NoValidStateSettings(Settings):
            token: str = json_setting(name="token", default=NO_DEFAULT, eq="x")

    assert str(info.value) == (
        "invalid defaults in NoValidStateSettings:\n  - token: value None must be equal to 'x'"
    )


def test_non_callable_validator_fails_the_class_statement():
    """A validator that cannot be called is refused on the spot."""
    with pytest.raises(TypeError) as info:

        class NotCallableSettings(Settings):
            port: int = json_setting(name="port", default=1, validator=5)

    assert str(info.value) == "validator must be callable, got int"


def test_conflicting_constraint_parameters_fail_the_class_statement():
    """Ordering bounds and string bounds do not mix on one member."""
    with pytest.raises(TypeError) as info:

        class ConflictingSettings(Settings):
            name: str = json_setting(name="name", default="x", gt=1, min_length=2)

    assert str(info.value) == (
        "conflicting constraints: gt compare the value, "
        "while min_length apply to strings and lengths"
    )


def test_bad_regex_fails_the_class_statement():
    """A pattern that does not compile is refused on the spot. The tail of
    the message is the re module's own wording, so the check pins the
    prefix the library composes."""
    with pytest.raises(ValueError) as info:

        class BadRegexSettings(Settings):
            code: str = json_setting(name="code", default="x", regex="[")

    assert str(info.value).startswith("Invalid regex '['")


def test_orphan_member_reference_fails_the_class_statement():
    """A bound must reference a member of the same class. An attribute object that
    no member of the class carries is refused, and the error names it.
    """
    orphan = non_storage_setting(default=1)  # an attribute bound to no member
    with pytest.raises(TypeError) as info:

        class OrphanSettings(Settings):
            value: int = non_storage_setting(default=2, ge=orphan)

    assert str(info.value) == (
        "OrphanSettings: the ge= of 'value' references an attribute that is not declared as a "
        "member by any settings class. Assign the attribute to a member of this class first"
    )
