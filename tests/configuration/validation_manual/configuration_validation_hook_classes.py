"""The configuration classes of the validation-hook scenarios.

Every class belongs to exactly one test. A configuration class keeps the
values that an earlier load gave it, so a class is never shared between
tests.

Everything that a comparison cannot express (conditional requirements, "at
least one of", and invariants) goes into the class hook ``__validate__``.
The hook reads the whole configuration object and returns a dict that maps
a member name to a problem (an empty dict means that the class is fine).

In this read-only package, the hook runs in the cross-member step of the
load, always on a fully built object. It reads and reports, and it never
fixes anything. An exception that its body raises propagates as it is,
because it is a bug in the code of the hook, not a property of the values.
"""

from configuration_validation_storage_paths import STORAGE_DIR

from advexp.configuration import REQUIRED, Configuration, constant_setting
from advexp.configuration.plugins.environment.variables import (
    env_source,
)
from advexp.configuration.plugins.json_settings import json_setting, json_source

HOOK_UNSETTLED_JSON_FILE = STORAGE_DIR / "hook-unsettled.json"
HOOK_FATAL_JSON_FILE = STORAGE_DIR / "hook-fatal.json"


class HookedUnsettledConfiguration(
    Configuration,
    options=json_source(file=HOOK_UNSETTLED_JSON_FILE),
):
    """Production mode demands an explicit ``ssl`` setting. The finding names the
    member, and the load resets that member. The finding then comes back,
    because no reset can settle it, so the pass aborts.
    """

    mode: str = json_setting(name="mode", default="dev")
    ssl: str = json_setting(name="ssl", default="none")

    def __validate__(self) -> dict:
        if self.mode == "prod" and self.ssl != "on":
            return {"ssl": "ssl must be 'on' in production mode"}
        return {}


class HookedFatalConfiguration(
    Configuration,
    options=json_source(file=HOOK_FATAL_JSON_FILE),
):
    """The same rule with a required member: the finding aborts the load."""

    mode: str = json_setting(name="mode", default="dev")
    ssl: str = json_setting(name="ssl", default=REQUIRED)

    def __validate__(self) -> dict:
        if self.mode == "prod" and self.ssl != "on":
            return {"ssl": "ssl must be 'on' in production mode"}
        return {}


class HookBadReturnConfiguration(
    Configuration,
    options=env_source(),
):
    """A hook that returns a value of the wrong kind: the check of the load itself
    refuses the return value.
    """

    value: int = constant_setting(default=1)

    # no return annotation on purpose: this hook exists to break the
    # contract, and an honest "-> dict" would be a lie the checkers flag
    def __validate__(self):
        return "not a dict"


class HookExplodingConfiguration(
    Configuration,
    options=env_source(),
):
    """A hook that raises an exception instead of reporting a finding. The
    exception is a bug in the code of the hook, and the load lets it through as
    it is.
    """

    mode: str = constant_setting(default="dev")

    def __validate__(self) -> dict:
        raise ZeroDivisionError("hook bug")


class HookUnreadMemberConfiguration(
    Configuration,
    options=env_source(),
):
    """A hook that reads a member that nothing has loaded: the load reports the own
    miss of the member, next to the read error that the hook met.
    """

    mode: str = constant_setting(default="dev")
    missing: int

    def __validate__(self) -> dict:
        if self.missing == 1:
            return {}
        return {}
