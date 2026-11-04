"""The read-only contract: every write path names the reload call.

The package never writes a value back. This is the main difference between
it and the settings package of the same family. Assigning to a member and
deleting a member meet the same error: the member is read-only, and the
message names the call that stands in for the write,
``load_configuration``.

The contract holds over the members themselves, whether they are loaded or
not, so the test never touches the file of the class.
"""

import pytest
from configuration_read_only_classes import ReadOnlyConfiguration


def test_writing_a_member_names_the_read_only_contract():
    """Assigning and deleting both refuse, each naming the member and the
    reload call."""
    with pytest.raises(TypeError) as assigned:
        ReadOnlyConfiguration.answer = 5
    assert str(assigned.value) == (
        "'answer' is a read-only member of ReadOnlyConfiguration: configuration values are loaded "
        "from their sources and cannot be assigned. Call load_configuration() to reload them"
    )

    with pytest.raises(TypeError) as deleted:
        del ReadOnlyConfiguration.known
    assert str(deleted.value) == (
        "'known' is a read-only member of ReadOnlyConfiguration: configuration values are loaded "
        "from their sources and cannot be assigned. Call load_configuration() to reload them"
    )

    # nothing changed: the declared default stands
    assert ReadOnlyConfiguration.known == 7
