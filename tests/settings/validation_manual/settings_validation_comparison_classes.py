"""The settings classes of the comparison-constraint scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

The comparison parameters ``gt/ge/lt/le/eq/ne`` are declared as keyword
parameters of the setting. ``None`` passes every comparison silently, except
``eq`` and ``ne``, where it takes part in the comparison. A ``NO_DEFAULT``
member serves ``None``, so an ``eq`` bound on such a member would leave it
with no valid state, and the ``class`` statement refuses it (the declaration
category pins this). The ``eq`` member below therefore declares its default.
"""

from settings_validation_storage_paths import STORAGE_DIR

from advexp.settings import REQUIRED, Settings
from advexp.settings.plugin_api import NO_DEFAULT
from advexp.settings.plugins.environment.variables import environment_variable_setting
from advexp.settings.plugins.json_settings import json_setting, json_source

SIX_COMPARISONS_JSON_FILE = STORAGE_DIR / "comparison-six.json"
PORT_REQUIRED_JSON_FILE = STORAGE_DIR / "comparison-port.json"
INCOMPARABLE_JSON_FILE = STORAGE_DIR / "comparison-incomparable.json"
CLEAN_JSON_FILE = STORAGE_DIR / "comparison-clean.json"


class SixComparisonsSettings(
    Settings,
    options=json_source(file=SIX_COMPARISONS_JSON_FILE),
):
    """One member per comparison parameter; the storage violates all six."""

    gt_member: int = json_setting(name="gt_member", default=NO_DEFAULT, gt=10)
    ge_member: int = json_setting(name="ge_member", default=NO_DEFAULT, ge=10)
    lt_member: int = json_setting(name="lt_member", default=NO_DEFAULT, lt=10)
    le_member: int = json_setting(name="le_member", default=NO_DEFAULT, le=10)
    # eq participates in the None check, so this member needs a default
    eq_member: int = json_setting(name="eq_member", default=10, eq=10)
    ne_member: int = json_setting(name="ne_member", default=NO_DEFAULT, ne=10)


class PortRequiredSettings(
    Settings,
    options=json_source(file=PORT_REQUIRED_JSON_FILE),
):
    """A required member whose stored value breaks its ``le`` bound."""

    port: int = json_setting(name="port", default=REQUIRED, le=65535)


class IncomparableLabelSettings(
    Settings,
    options=json_source(file=INCOMPARABLE_JSON_FILE),
):
    """A string member against a numeric bound: no comparison can run."""

    label: str = json_setting(name="label", default=NO_DEFAULT, gt=10)


class CleanComparisonSettings(
    Settings,
    options=json_source(file=CLEAN_JSON_FILE),
):
    """A satisfied ``gt`` bound: the passing side of the comparison story."""

    pass_check: int = json_setting(name="pass_check", default=NO_DEFAULT, gt=10)


class EnvPortSettings(Settings):
    """The same ``le`` bound reading an environment variable: the
    constraints are declared on the member, not on the backend."""

    port: int = environment_variable_setting(name="VM_PORT", default=8080, le=65535)
