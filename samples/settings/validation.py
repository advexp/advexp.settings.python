"""
Example: validation in Advexp.Settings, the full tour.

The sample shows every capability on one minimal backend:

- the field constraints of a member (bounds, lengths, regex, and a custom
  validator);
- the rules across members (a comparison bound that references a member,
  ``when=`` conditions, and the ``__validate__`` hook);
- the points at which the checks run: class creation (the declared defaults
  against the comparison rules; the hook joins later), assignment, a load
  (lenient), updates and saves (strict), and the manual
  ``validate_settings()``.

Run from the repository root with the package installed
(``pip install advexp-settings``):

    python samples/settings/validation.py

The backend is the minimal in-memory one in ``backends/memory.py`` next to
this file. (The API tour ``settings_api.py`` runs on the bundled plugins
instead.)
"""

import logging
from typing import Any, List, Optional

# the minimal local backend this tour runs on (an attribute, a serializer
# and a plugin object on the public contracts; importing the package
# enables it, the bundled plugins' way)
from backends import MemoryStorage, memory_setting

import advexp.settings as adv_settings

# ---------------------------------------------------------------------------
# The tour
# ---------------------------------------------------------------------------


def _is_simple_tag(value: Any) -> bool:
    """A custom validator: returns whether the value passes (True) or not."""
    return isinstance(value, str) and value.islower() and value.isalnum()


class FieldSettings(adv_settings.Settings):
    """One member for each field constraint: bounds, lengths, regex, and validator.

    ``None`` passes the ordering, length, and regex constraints silently, because
    it is the value of an unset ``Optional`` member. It does take part in
    ``eq``/``ne``.
    """

    port: int = memory_setting(name="f.port", default=8080, ge=1, le=65535)
    mirror: str = memory_setting(name="f.mirror", default="eu-1", ne="backup")
    tags: List[str] = memory_setting(name="f.tags", default=["primary"], min_length=1)
    host: str = memory_setting(name="f.host", default="db.internal", regex=r"^[\w.-]+$")
    tag: str = memory_setting(name="f.tag", default="primary", validator=_is_simple_tag)
    token: Optional[adv_settings.SecretStr] = memory_setting(
        name="f.token", default=None, min_length=8
    )


class RangeSettings(adv_settings.Settings):
    """A rule across members: the ``ge=`` bound references ``min_port``, the
    attribute of a member that was declared earlier.

    The value is compared with the current value of that member wherever the
    whole class is checked at once.
    """

    min_port: int = memory_setting(name="r.min", default=1024)
    max_port: int = memory_setting(name="r.max", default=65535, ge=min_port)


class SecureSettings(adv_settings.Settings):
    """A ``when=`` condition and the class hook together.

    The ``eq=`` bound applies only when ``ssl`` is true. The hook carries the
    conditional requirement that a comparison cannot state.

    The hook always reads a fully built settings object. It reports problems
    through a dict that maps a member name to a problem (an empty dict passes),
    and it must not try to fix values: fixing is the job of the load pass.
    """

    ssl: bool = memory_setting(name="s.ssl", default=False)
    # eq=443 is checked only while ssl is truthy; while it is falsy, none
    # of port's constraints apply
    port: int = memory_setting(name="s.port", default=80, eq=443, when=ssl)
    mode: str = memory_setting(name="s.mode", default="dev")
    log_file: Optional[str] = memory_setting(name="s.log", default=None)

    def __validate__(self) -> dict:
        if self.mode == "production" and self.log_file is None:
            return {"log_file": "log_file is required in production mode"}
        return {}


class WaitingSettings(adv_settings.Settings):
    """A member without a default holds no value until it is assigned or loaded.
    The rule that references it waits, instead of comparing against nothing.
    """

    floor: int = memory_setting(name="w.floor")
    ceil: int = memory_setting(name="w.ceil", default=100, ge=floor)


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # the library reports soft findings (load fallbacks, resets) as
    # warnings on the "advexp.settings" logger; basicConfig keeps them in
    # the print order of the tour
    logging.basicConfig(level=logging.INFO, format="log: %(message)s")
    adv_settings.LibraryConfiguration.set_log_level(logging.INFO)

    section("field constraints: declared on the member, enforced everywhere")
    print(f"port  = {FieldSettings.port!r} (the default, within the bounds)")
    for member, bad in [
        ("port", 70000),
        ("mirror", "backup"),
        ("tags", []),
        ("host", "not a host"),
        ("tag", "Upper!"),
    ]:
        try:
            setattr(FieldSettings, member, bad)
        except adv_settings.SettingValidationError as error:
            print(f"{member:<6} rejected: {error}")
    # None passes the length constraint silently; the secret stays masked
    FieldSettings.token = None
    print("token = None (None is accepted silently for an Optional member)")
    FieldSettings.reset_settings()

    section("an invalid default fails the class statement itself")
    try:

        class BadDefaults(adv_settings.Settings):
            port: int = memory_setting(default=70000, le=65535)
            lo: int = memory_setting(default=100)
            hi: int = memory_setting(default=10, ge=lo)

    except TypeError as error:
        print(f"BadDefaults rejected at creation:\n{error}")

    section("a stand-in None the constraints reject fails the class too")
    try:

        class BadStandIn(adv_settings.Settings):
            # a member without a default serves None while no value has
            # arrived, and eq= refuses it: without an assignment the member
            # could never hold a valid value — REQUIRED is its honest spelling
            token: Optional[str] = memory_setting(eq="fixed")

    except TypeError as error:
        print(f"BadStandIn rejected at creation:\n{error}")

    section("a bad declaration fails the declaration site")
    try:

        class BadWhen(adv_settings.Settings):
            value: int = memory_setting(default=1, when=True)

    except TypeError as error:
        print(f"BadWhen rejected: {error}")

    section("rules across members: references and the manual check")
    print(
        f"ports = min={RangeSettings.min_port!r}, max={RangeSettings.max_port!r} (defaults agree)"
    )
    RangeSettings.validate_settings()  # quiet: the class is consistent
    RangeSettings.min_port = 70000  # an assignment checks the member's own bounds only
    try:
        RangeSettings.validate_settings()
    except adv_settings.SettingValidationError as error:
        print(f"manual check rejected the pair:\n{error}")
        print(f"problems = {error.problems} (the report as data, for a CLI or a test)")
    RangeSettings.min_port = 1024

    section("when=: the member's constraints wake up with the neighbor")
    print(f"port  = {SecureSettings.port!r} (ssl is off, so the eq=443 constraint is not applied)")
    SecureSettings.port = 8080  # accepted: the condition is falsy
    SecureSettings.ssl = True
    try:
        SecureSettings.port = 8081  # eq=443 is awake now
    except adv_settings.SettingValidationError as error:
        print(f"assignment rejected: {error}")
    SecureSettings.port = 443
    print(f"port  = {SecureSettings.port!r} (eq=443 is satisfied with ssl enabled)")

    section("a load is soft: the violated rule's members fall back to defaults")
    MemoryStorage.data["r.min"] = 20000
    MemoryStorage.data["r.max"] = 1000  # < min: the stored pair disagrees
    # warning logged, members reset — and the fallback is an entry of the
    # report load_settings returns, so the finding is data, not a log line
    report = RangeSettings.load_settings()
    print(
        f"ports = min={RangeSettings.min_port!r}, max={RangeSettings.max_port!r}"
        "(back to the defaults)"
    )
    for entry in report:
        print(f"{type(entry).__name__}: {entry}")
    RangeSettings.delete_settings()

    section("an update is strict: checked over the new values beside the current ones")
    try:
        RangeSettings.update_from_dict({"min_port": 30000})  # 65535 >= 30000 holds...
    except adv_settings.SettingValidationError as error:
        print(f"update rejected: {error.problems}")
    RangeSettings.update_from_dict({"min_port": 20000, "max_port": 30000})  # the pair moves
    print(
        f"ports = min={RangeSettings.min_port!r}, max={RangeSettings.max_port!r}"
        "(both changed together)"
    )

    section("a save is strict too: a class in violation saves nothing")
    RangeSettings.__settings_values__["max_port"] = 1000  # 1000 < 2000: broken on purpose
    try:
        RangeSettings.save_settings()
    except adv_settings.SettingValidationError as error:
        print(f"save rejected: {error.problems}")
    assert "r.max" not in MemoryStorage.data  # nothing was written
    RangeSettings.reset_settings()

    section("the __validate__ hook joins every report")
    SecureSettings.mode = "production"
    try:
        SecureSettings.save_settings()
    except adv_settings.SettingValidationError as error:
        print(f"save rejected by the hook, nothing written: {error.problems}")
    SecureSettings.log_file = "/var/log/app.log"
    SecureSettings.save_settings()
    print(
        f"the storage contains the class once the hook check passes: "
        f"{MemoryStorage.data['s.log']!r}"
    )
    SecureSettings.delete_settings()

    section("a secret neighbor stays masked in the messages")

    class Masked(adv_settings.Settings):
        token: adv_settings.SecretStr = memory_setting(default=adv_settings.SecretStr("s3cr3t"))
        echo: str = memory_setting(default="s3cr3t", eq=token)

    Masked.__settings_values__["echo"] = "leak"  # the pair breaks
    try:
        Masked.validate_settings()
    except adv_settings.SettingValidationError as error:
        print(f"masked: {error}")  # the token shows as '**********', never 's3cr3t'

    section("a rule whose member holds no value waits")
    print(f"ceil  = {WaitingSettings.ceil!r} (floor has no value, so the rule does not apply)")
    WaitingSettings.floor = 50
    WaitingSettings.validate_settings()  # 100 >= 50 holds
    print("floor = 50: the rule applies once the member has a value")
    WaitingSettings.floor = 500
    try:
        WaitingSettings.validate_settings()  # 100 < 500
    except adv_settings.SettingValidationError as error:
        print(f"the rule fires now: {error.problems}")


if __name__ == "__main__":
    main()
