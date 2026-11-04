"""
Example: validation in Advexp.Configuration, the full tour.

The sample shows every capability on the environment variables source:

- required and optional members;
- the field constraints (bounds, lengths, regex, and a custom validator);
- the rules across members (a comparison bound that references a member,
  ``when=`` conditions, and the ``__validate__`` hook);
- the reporting of load errors. The failures of a required member abort the
  load in one ``adv_config.AggregateLoadError``, which carries an entry for
  each member. The failures of an optional member go into the report that
  ``load_configuration`` returns, and the member stands at its default.

Run from the repository root with the package installed
(``pip install advexp-configuration``):

    python samples/configuration/validation.py
"""

import logging
import os
from typing import Any, List, Optional

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.variables as env


def _is_simple_tag(value: Any) -> bool:
    """A custom validator: returns whether the value passes (True) or not."""
    return isinstance(value, str) and value.islower() and value.isalnum()


class FieldConfig(
    adv_config.Configuration,
    options=env.env_source(),
):
    """One member for each field constraint: bounds, lengths, regex, and validator.

    A member without ``default=`` is required (the ``default`` parameter of the
    source is itself ``REQUIRED``). An explicit ``default=`` (a value or
    ``None``) makes the member optional. ``None`` passes the ordering, length,
    and regex constraints silently, but it takes part in ``eq``/``ne``.
    """

    port: int = env.environment_variable_setting(name="VAL_PORT", default=8080, ge=1, le=65535)
    mirror: str = env.environment_variable_setting(name="VAL_MIRROR", default="eu-1", ne="backup")
    tags: List[str] = env.environment_variable_setting(
        name="VAL_TAGS", default=["primary"], min_length=1
    )
    host: str = env.environment_variable_setting(
        name="VAL_HOST", default="db.internal", regex=r"^[\w.-]+$"
    )
    tag: str = env.environment_variable_setting(
        name="VAL_TAG", default="primary", validator=_is_simple_tag
    )
    note: Optional[str] = env.environment_variable_setting(name="VAL_NOTE", default=None)


class RangeConfig(
    adv_config.Configuration,
    options=env.env_source(),
):
    """A rule across members: the ``ge=`` bound references ``min_port``, the
    attribute of a member that was declared earlier.

    After the load, the value is compared with the current value of that member.
    A violation is reported in the own error shape of the package: one more entry
    of the abort.
    """

    min_port: int = env.environment_variable_setting(name="VAL_MIN_PORT", default=1024)
    max_port: int = env.environment_variable_setting(
        name="VAL_MAX_PORT", default=65535, ge=min_port
    )


class SecureConfig(
    adv_config.Configuration,
    options=env.env_source(),
):
    """A ``when=`` condition and the class hook together.

    The ``eq=`` bound applies only when ``ssl`` is true. The hook carries the
    conditional requirement that a comparison cannot state. It reads the fully
    built configuration and reports problems through a dict that maps a member
    name to a problem.
    """

    ssl: bool = env.environment_variable_setting(name="VAL_SSL", default=False)
    # eq=443 is checked only while ssl is truthy; while it is falsy, none
    # of port's constraints apply
    port: int = env.environment_variable_setting(name="VAL_SSL_PORT", default=80, eq=443, when=ssl)
    mode: str = env.environment_variable_setting(name="VAL_MODE", default="dev")
    log_file: Optional[str] = env.environment_variable_setting(name="VAL_LOG_FILE", default=None)

    def __validate__(self) -> dict:
        if self.mode == "production" and self.log_file is None:
            return {"log_file": "log_file is required in production mode"}
        return {}


def section(title: str) -> None:
    print(f"\n--- {title} ---", flush=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="log: %(message)s")
    adv_config.LibraryConfiguration.set_log_level(logging.INFO)

    section("a clean load: defaults inside their bounds, nothing to report")
    report = FieldConfig.load_configuration()
    print(f"port  = {FieldConfig.port!r}, host = {FieldConfig.host!r} (defaults)")
    print(
        f"report = {report} (no required member failed and nothing fell back to a default:"
        "the report is empty)"
    )

    section("optional members fall back — and the load returns their report")
    # port and tags have defaults: their violations do not abort the load;
    # the members stand at their defaults with a warning, and the fallbacks
    # are the report load_configuration returns — the same entries a
    # required member would carry into its abort
    os.environ["VAL_PORT"] = "70000"  # violates le=65535
    os.environ["VAL_TAGS"] = "[]"  # violates min_length
    report = FieldConfig.load_configuration()
    print(
        f"port  = {FieldConfig.port!r}, tags = {FieldConfig.tags!r} (optional "
        "members: defaults are used)"
    )
    for entry in report:
        print(f"{type(entry).__name__}: {entry}")
    for name in ("VAL_PORT", "VAL_TAGS"):
        del os.environ[name]

    section("a required member's violations are the abort's entries")

    class RequiredConfig(
        adv_config.Configuration,
        options=env.env_source(),
    ):
        port: int = env.environment_variable_setting(name="VAL_REQ_PORT", ge=1, le=65535)
        factor: int = env.environment_variable_setting(name="VAL_REQ_FACTOR")

    os.environ["VAL_REQ_PORT"] = "70000"  # violates le=65535, no default to serve
    os.environ["VAL_REQ_FACTOR"] = "abc"  # does not convert to int either
    try:
        RequiredConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"{type(entry).__name__}: {entry}")
    del os.environ["VAL_REQ_PORT"], os.environ["VAL_REQ_FACTOR"]

    section("an invalid default or a bad declaration fails the class statement")
    try:

        class BadDefaults(
            adv_config.Configuration,
            options=env.env_source(),
        ):
            lo: int = env.environment_variable_setting(default=100)
            hi: int = env.environment_variable_setting(default=10, ge=lo)

    except TypeError as error:
        print(f"BadDefaults rejected at creation:\n{error}")

    try:

        class BadStandIn(
            adv_config.Configuration,
            options=env.env_source(),
        ):
            # the None of an explicit default is checked at class creation
            # like any value, and eq= refuses it: the member could never be
            # valid as optional — leaving out default= (required) is its
            # honest spelling
            mode: Optional[str] = env.environment_variable_setting(
                name="VAL_STAND_IN", default=None, eq="prod"
            )

    except TypeError as error:
        print(f"BadStandIn rejected at creation:\n{error}")

    try:

        class BadWhen(
            adv_config.Configuration,
            options=env.env_source(),
        ):
            value: int = env.environment_variable_setting(default=1, when=True)

    except TypeError as error:
        print(f"BadWhen rejected: {error}")

    section("a rule across members rides the same abort")
    os.environ["VAL_MIN_PORT"] = "20000"
    os.environ["VAL_MAX_PORT"] = "1000"  # < min: the loaded pair disagrees
    try:
        RangeConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"{type(entry).__name__}: {entry}")
    del os.environ["VAL_MIN_PORT"], os.environ["VAL_MAX_PORT"]

    section("when= gates the constraints; the hook reports through the abort too")
    os.environ["VAL_SSL"] = "1"
    os.environ["VAL_MODE"] = "production"  # log_file stays unset: the hook fires
    try:
        SecureConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"{type(entry).__name__}: {entry}")

    os.environ["VAL_LOG_FILE"] = "/var/log/app.log"
    # the hook is satisfied now, but eq=443 is awake under ssl: even the
    # member's own default 80 violates it — a conditional rule judges the
    # loaded state, not only what the source provided
    try:
        SecureConfig.load_configuration()
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"{type(entry).__name__}: {entry}")

    os.environ["VAL_SSL_PORT"] = "443"
    SecureConfig.load_configuration()  # everything agrees: quiet
    print(f"port  = {SecureConfig.port!r} (443 with ssl enabled; the hook check passed)")
    for name in ("VAL_SSL", "VAL_MODE", "VAL_LOG_FILE", "VAL_SSL_PORT"):
        del os.environ[name]

    section("a rule whose member holds no value waits")

    class WaitingConfig(
        adv_config.Configuration,
        options=env.env_source(),
    ):
        floor: int = env.environment_variable_setting(name="VAL_FLOOR")  # required, unset
        ceil: int = env.environment_variable_setting(name="VAL_CEIL", default=100, ge=floor)

    try:
        WaitingConfig.load_configuration()  # floor is missing; the rule waits
    except adv_config.AggregateLoadError as error:
        for entry in error.errors:
            print(f"{type(entry).__name__}: {entry}")
    print("(ceil has no second error: the rule is not checked while floor has no value)")


if __name__ == "__main__":
    main()
