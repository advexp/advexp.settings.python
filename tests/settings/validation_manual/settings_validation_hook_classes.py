"""The settings classes of the validation-hook scenarios.

Every class belongs to exactly one test. A settings class keeps the values
that an earlier load gave it, so a class is never shared between tests.

Everything that a comparison cannot express (conditional requirements, "at
least one of", and invariants) goes into the class hook ``__validate__``.
The hook reads the whole settings object and returns a dict that maps a
member name to a problem (an empty dict means that the class is fine).

- The hook runs wherever the cross-member checks run, always on a fully
  built settings object.
- It reads and reports, and it never fixes anything.
- An exception that its body raises propagates as it is, because it is a bug
  in the code of the hook, not a property of the values.
- Reading a member that holds no value is the finding of that member.
"""

from settings_validation_storage_paths import STORAGE_DIR

from advexp.settings import REQUIRED, Settings, non_storage_setting
from advexp.settings.plugins.environment.variables import (
    environment_variable_setting,
)
from advexp.settings.plugins.json_settings import json_setting, json_source

HOOK_UNSETTLED_JSON_FILE = STORAGE_DIR / "hook-unsettled.json"
HOOK_FATAL_JSON_FILE = STORAGE_DIR / "hook-fatal.json"


class HookedUnsettledSettings(
    Settings,
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


class HookedFatalSettings(
    Settings,
    options=json_source(file=HOOK_FATAL_JSON_FILE),
):
    """The same rule with a required member: the finding aborts the load."""

    mode: str = json_setting(name="mode", default="dev")
    ssl: str = json_setting(name="ssl", default=REQUIRED)

    def __validate__(self) -> dict:
        if self.mode == "prod" and self.ssl != "on":
            return {"ssl": "ssl must be 'on' in production mode"}
        return {}


class HookBadReturnSettings(Settings):
    """A hook that answers with a value of the wrong kind: the check itself
    refuses the return value.
    """

    value: int = non_storage_setting(default=1)

    # no return annotation on purpose: this hook exists to break the
    # contract, and an honest "-> dict" would be a lie the checkers flag
    def __validate__(self):
        return "not a dict"


class HookExplodingSettings(Settings):
    """A hook that raises an exception instead of reporting a finding. The
    exception is a bug in the code of the hook, and every checkpoint lets it
    through as it is.
    """

    mode: str = non_storage_setting(default="dev")

    def __validate__(self) -> dict:
        raise ZeroDivisionError("hook bug")


class HookUnreadMemberSettings(Settings):
    """A hook that reads a member that nothing has loaded: the read is the finding
    of that member, in the report of every checkpoint that runs the hook.
    """

    mode: str = non_storage_setting(default="dev")
    # the variable stays unset: the member holds no value for the hook to meet
    missing: int = environment_variable_setting(name="ADVEXP_MANUAL_HOOK_MISSING", default=REQUIRED)

    def __validate__(self) -> dict:
        if self.missing == 1:
            return {}
        return {}


class HookUnreadMemberLoadSettings(Settings):
    """The same hook at a load: the own miss of the member and the read of it by
    the hook go into the abort together.
    """

    mode: str = non_storage_setting(default="dev")
    # the variable stays unset: the member holds no value for the hook to meet
    missing: int = environment_variable_setting(name="ADVEXP_MANUAL_HOOK_MISSING", default=REQUIRED)

    def __validate__(self) -> dict:
        if self.missing == 1:
            return {}
        return {}
