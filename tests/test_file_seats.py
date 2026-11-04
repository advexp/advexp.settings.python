# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The file-seat registry: the seat of any family is refused next to its own
source.

The file seat of a family names the file of the members of that family in
the class, when the builder of another family holds the binding. Next to
the source binding of its own family, the pair would name one storage twice,
and the ``class`` statement refuses it.

This refusal is not a special case of any bundled family. It is driven by
the registry into which every family registers its pair, and this module
tests that registry with a family of its own.
"""

from __future__ import annotations

import pytest

from advexp.settings import Settings
from advexp.settings_base.sources import register_file_seat, register_source_link_key

FILE_SEAT = "TestFileSeatFile"
SOURCE_SEAT = "TestFileSeatSource"

# the family registers once for the module: the registry has no
# unregister, the bundled families' rule
register_source_link_key(SOURCE_SEAT)
register_file_seat(FILE_SEAT, SOURCE_SEAT)


def test_a_registered_seat_is_refused_beside_its_source():
    # the class statement refuses the pair of a registered family the
    # same line it refuses the bundled ones, whatever built the entries
    with pytest.raises(
        TypeError,
        match=(
            "Guarded declares the family's file seat 'TestFileSeatFile' alongside "
            "its source binding "
            "'TestFileSeatSource'. For a bound family, the file must be given on its source "
            "builder"
        ),
    ):

        class Guarded(
            Settings,
            options={SOURCE_SEAT: "bound", FILE_SEAT: "seated"},
        ):
            pass


def test_registering_the_same_pair_again_is_a_no_op():
    register_file_seat(FILE_SEAT, SOURCE_SEAT)


def test_a_seat_claimed_for_another_source_is_a_conflict():
    with pytest.raises(ValueError, match="is already registered for the source seat"):
        register_file_seat(FILE_SEAT, "TestFileSeatOtherSource")


def test_a_seat_cannot_name_an_unregistered_source():
    with pytest.raises(ValueError, match="which no family has registered"):
        register_file_seat("TestUnregisteredFile", "TestNoSuchSource")
