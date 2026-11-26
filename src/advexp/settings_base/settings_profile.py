# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The settings profiles: named flavors of the settings files.

A settings profile is declared from one environment variable and is spelled
as a named slot of a templated file path — one file per profile, the
``appsettings.{env}.json`` convention:

```python
profile = settings_profile("APP_ENV", choices=("dev", "test", "prod"))

json_source(file="settings-{APP_ENV}.json", settings_profile=profile)
```

The name of the slot in the template is the name of the variable. ``slot=``
renames it if the template spells another name.

The whitelist ``choices`` is obligatory, and it is checked before any file
is touched. A typo such as ``APP_ENV=prodd`` therefore fails the load with a
clear error, instead of quietly turning into a missing file that the chain
would walk past.

A variable that is not set resolves through the declared ``default=``. The
default must be explicit in the declaration, because implicit environments
are how a production process ends up running on development values. A
variable that is neither set nor defaulted breaks the link: the load pass
aborts in the same way as for any broken source, and the links below never
hide the problem.

The resolution is made per pass. Every pass reads its variables anew, and no
cache outlives a pass. One pass resolves each variable once, and it writes a
debug record that names the variable, its value, and the file that it
produced.
"""

from __future__ import annotations

import os
import re
from typing import Callable, Dict, Optional, Sequence, Tuple, Union

from advexp.settings_base.context import SettingsContext
from advexp.settings_base.user_facing_error import UserFacingError

SLOT_SPELLING = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
"""The spelling of one template slot: an identifier in braces. A brace
pair that does not spell an identifier — ``{}``, ``{1}``, ``{a b}`` — is
not a slot and stays the literal text of the template, so a file name
carrying such braces needs no escaping."""


def template_slots(text: str) -> Tuple[str, ...]:
    """The slot names a template spells, each once, in order of appearance."""
    names: Dict[str, None] = {}
    for match in SLOT_SPELLING.finditer(text):
        names[match.group(1)] = None
    return tuple(names)


class SettingsProfile:
    """One settings profile: a named slot of a templated path whose value
    one environment variable provides.

    It is built by :func:`settings_profile`; an application never constructs one
    directly.

    - ``variable`` names the environment variable.
    - ``slot_name`` is the slot that the template spells for the variable. It is
      the name of the variable unless ``slot=`` renamed it, and it is the name
      by which every check between the template and the profile goes.
    - ``choices`` is the whitelist of the variable.
    - ``default`` is the value to which an unset variable resolves. It is already
      known to be one of the choices, or it is ``None`` if none was declared.
    """

    def __init__(
        self,
        variable: str,
        choices: Tuple[str, ...],
        default: Optional[str] = None,
        slot_name: Optional[str] = None,
    ) -> None:
        self.__variable = variable
        self.__choices = choices
        self.__default = default
        self.__slot_name = slot_name if slot_name is not None else variable

    @property
    def variable(self) -> str:
        """The environment variable the parameter reads."""
        return self.__variable

    @property
    def choices(self) -> Tuple[str, ...]:
        """The whitelist of values the variable may hold."""
        return self.__choices

    @property
    def default(self) -> Optional[str]:
        """The value an unset variable resolves to; ``None`` when the
        parameter declares no default."""
        return self.__default

    @property
    def slot_name(self) -> str:
        """The slot name the template spells for this parameter."""
        return self.__slot_name

    def __repr__(self) -> str:
        return f"SettingsProfile({self.__variable!r}, choices={self.__choices!r})"


def settings_profile(
    variable: str,
    choices: Sequence[str],
    default: Optional[str] = None,
    slot: Optional[str] = None,
) -> SettingsProfile:
    """Declare one settings profile that is read from an environment variable.

    Pass the result to the ``settings_profile=`` of a builder of a source that carries
    a file, either alone or in a tuple:

    ```python
    app_env = settings_profile("APP_ENV", choices=("dev", "test", "prod"))

    class AppConfig(Configuration, options=Sources(
        json_source(file="app.json"),
        json_source(file="settings-{APP_ENV}.json", settings_profile=profile),
    )):
    ```

    ``variable`` names the environment variable, and the template spells the
    slot by that name: ``settings-{APP_ENV}.json``.

    ``slot=`` renames the slot if the template spells another name. The value
    still comes from ``variable``, and the template spells the renamed slot, so
    ``slot="env"`` reads ``APP_ENV`` into ``settings-{env}.json``. This is
    useful for a template that dictates its own slot names (a file shared with
    another system, or a path that reads better with a short slot). The name
    must be a valid identifier: otherwise, the braces would stay as literal text
    instead of becoming a slot.

    ``choices`` is the obligatory whitelist of which the value of the variable
    must be one. It is checked before any file is touched.

    ``default`` is the value to which an unset variable resolves. It must be one
    of the choices. Without it, an unset variable breaks the link at load time.
    """
    if not isinstance(variable, str) or not variable:
        raise TypeError(
            f"settings_profile(variable=...) expects a non-empty variable name, got {variable!r}"
        )
    if isinstance(choices, (str, bytes)) or not isinstance(choices, Sequence):
        raise TypeError(
            "settings_profile(choices=...) expects a sequence of allowed values, "
            f"got {type(choices).__name__}"
        )
    if not choices:
        raise TypeError(
            "settings_profile(choices=...) declares no allowed values. The whitelist "
            "protects the variable against typos such as APP_ENV=prodd"
        )
    for value in choices:
        if not isinstance(value, str) or not value:
            raise TypeError(
                f"settings_profile(choices=...) expects non-empty strings, got {value!r}"
            )
    if len(set(choices)) != len(choices):
        raise TypeError(
            f"settings_profile(choices=...) contains a duplicate value: {tuple(choices)!r}"
        )
    if default is not None:
        if not isinstance(default, str):
            raise TypeError(
                f"settings_profile(default=...) expects a string or None, got {default!r}"
            )
        if default not in choices:
            raise TypeError(
                f"settings_profile(default={default!r}) is not one of the declared "
                f"choices {tuple(choices)!r}"
            )
    slot_name = variable if slot is None else slot
    if not isinstance(slot_name, str) or not SLOT_SPELLING.fullmatch("{" + slot_name + "}"):
        raise TypeError(
            f"settings_profile(slot=...) expects a slot name that is a valid identifier, got {slot!r}"
        )
    return SettingsProfile(variable, tuple(choices), default, slot)


def link_settings_profile(
    profile: Optional[SettingsProfile],
    templates: Sequence[str],
    seat: str,
) -> Optional[Tuple[SettingsProfile, ...]]:
    """Check the ``settings_profile=`` of one builder against its templates.

    The source builders accept the declaration of one settings profile, or
    ``None``. The answer is the tuple that the link stores (``None`` for no
    profile at all).

    The check runs in both directions, and a failure fails the builder call:

    - A template slot that no profile declares leaves the path unresolvable.
      This includes the case in which ``settings_profile=`` is absent
      altogether.
    - A profile whose slot no template spells declares a variable that
      nothing reads.

    Both are spelling mistakes, and the builder call is the right place to
    report them.
    """
    if profile is None:
        normalized: Tuple[SettingsProfile, ...] = ()
    elif isinstance(profile, SettingsProfile):
        normalized = (profile,)
    else:
        raise TypeError(
            f"{seat} settings_profile= expects a settings_profile(...) result "
            f"or None, got {type(profile).__name__}"
        )
    declared: Dict[str, SettingsProfile] = {
        parameter.slot_name: parameter for parameter in normalized
    }
    spelled = {slot for template in templates for slot in template_slots(template)}
    unknown = sorted(spelled - set(declared))
    if unknown:
        raise TypeError(
            f"{seat} uses the slot(s) {', '.join('{%s}' % s for s in unknown)} "
            "in its template, but no settings_profile declares them. Pass the "
            "settings_profile of the builder"
        )
    unused = sorted(set(declared) - spelled)
    if unused:
        raise TypeError(
            f"{seat} declares the profile slot(s) "
            f"{', '.join('{%s}' % s for s in unused)}, "
            "but no slot in the template uses them. Remove the profile or add "
            "its slot to the template"
        )
    return normalized or None


def resolve_templated_path(
    context: SettingsContext,
    configured: Union[str, os.PathLike],
    profiles: Optional[Sequence[SettingsProfile]],
    source: str,
) -> str:
    """Return the configured spelling with its slots resolved for this pass.

    A spelling without a profile is returned as given: this is the plain file
    path that every unprofiled link spells. A templated spelling resolves
    its slot through the profile that declares it. The pass resolves
    each variable once and reuses the value for the rest of the pass, and it
    reads the environment anew on every pass.

    A variable that is not set breaks the link: a :class:`UserFacingError` names
    the variable, the template, and the source, unless the parameter declared a
    ``default=``. A value outside the whitelist breaks the link in the same way.
    The resolved value of every freshly resolved variable is written to the log
    as a debug record that names the file that it produced.
    """
    text = os.fspath(configured)
    if not profiles:
        return text
    by_slot = {profile.slot_name: profile for profile in profiles}
    fresh: Dict[str, str] = {}

    def reader(parameter: SettingsProfile) -> Callable[[], str]:
        def read() -> str:
            value = _read_variable(parameter, text, source)
            fresh[parameter.variable] = value
            return value

        return read

    values: Dict[str, str] = {}
    for slot in template_slots(text):
        parameter = by_slot.get(slot)
        if parameter is None:
            raise UserFacingError(
                ValueError(
                    f"{source} cannot resolve its parameterized file '{text}': "
                    f"the slot {{{slot}}} has no settings_profile declared"
                )
            )
        values[slot] = context.pass_parameter_value(parameter.variable, reader(parameter))
    unfolded = SLOT_SPELLING.sub(lambda match: values[match.group(1)], text)
    for variable, value in fresh.items():
        context.logger.debug(
            "the environment variable %s is set to %r; %s reads the file %r",
            variable,
            value,
            source,
            unfolded,
        )
    return unfolded


def _read_variable(parameter: SettingsProfile, template: str, source: str) -> str:
    """Return the whitelisted value of one variable, or the reason why it has none.

    The whitelist runs before any file is touched, and it guards the variable,
    not the file. A whitelisted value over a missing file is the normal miss of
    the chain. A value outside the whitelist is a typo, and the load names it in
    one message (with the variable, the template, and the source) instead of
    quietly walking past it.
    """
    value = os.environ.get(parameter.variable)
    if value is None:
        if parameter.default is None:
            raise UserFacingError(
                ValueError(
                    f"{source} cannot resolve its parameterized file '{template}': "
                    f"the environment variable {parameter.variable} is not set and "
                    "its settings_profile declares no default"
                )
            )
        return parameter.default
    if value not in parameter.choices:
        raise UserFacingError(
            ValueError(
                f"{source} cannot resolve its parameterized file '{template}': "
                f"the environment variable {parameter.variable} holds {value!r}, "
                f"which the declared choices {parameter.choices} do not allow"
            )
        )
    return value
