# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Path parameters that are read from environment variables.

A source link that carries a file may spell its file as a template with
named slots, and each slot reads its value from one environment variable:

```python
app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

json_source(file="settings-{APP_ENV}.json", parameters=app_env)
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


class EnvParameter:
    """One environment variable from which a templated path reads a slot.

    It is built by :func:`env_parameter`; an application never constructs one
    directly.

    - ``variable`` names the environment variable.
    - ``slot_name`` is the slot that the template spells for the variable. It is
      the name of the variable unless ``slot=`` renamed it, and it is the name
      by which every check between slots and parameters goes.
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
        return f"EnvParameter({self.__variable!r}, choices={self.__choices!r})"


def env_parameter(
    variable: str,
    choices: Sequence[str],
    default: Optional[str] = None,
    slot: Optional[str] = None,
) -> EnvParameter:
    """Declare one path parameter that is read from an environment variable.

    Pass the result to the ``parameters=`` of a builder of a source that carries
    a file, either alone or in a tuple:

    ```python
        app_env = env_parameter("APP_ENV", choices=("dev", "test", "prod"))

        class AppConfig(Configuration, options=Sources(
            json_source(file="app.json"),
            json_source(file="settings-{APP_ENV}.json", parameters=app_env),
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
            f"env_parameter(variable=...) expects a non-empty variable name, got {variable!r}"
        )
    if isinstance(choices, (str, bytes)) or not isinstance(choices, Sequence):
        raise TypeError(
            "env_parameter(choices=...) expects a sequence of allowed values, "
            f"got {type(choices).__name__}"
        )
    if not choices:
        raise TypeError(
            "env_parameter(choices=...) declares no allowed values. The whitelist "
            "protects the variable against typos such as APP_ENV=prodd"
        )
    for value in choices:
        if not isinstance(value, str) or not value:
            raise TypeError(f"env_parameter(choices=...) expects non-empty strings, got {value!r}")
    if len(set(choices)) != len(choices):
        raise TypeError(
            f"env_parameter(choices=...) contains a duplicate value: {tuple(choices)!r}"
        )
    if default is not None:
        if not isinstance(default, str):
            raise TypeError(f"env_parameter(default=...) expects a string or None, got {default!r}")
        if default not in choices:
            raise TypeError(
                f"env_parameter(default={default!r}) is not one of the declared "
                f"choices {tuple(choices)!r}"
            )
    slot_name = variable if slot is None else slot
    if not isinstance(slot_name, str) or not SLOT_SPELLING.fullmatch("{" + slot_name + "}"):
        raise TypeError(
            f"env_parameter(slot=...) expects a slot name that is a valid identifier, got {slot!r}"
        )
    return EnvParameter(variable, tuple(choices), default, slot)


def link_parameters(
    parameters: Union[EnvParameter, Sequence[EnvParameter], None],
    templates: Sequence[str],
    seat: str,
) -> Optional[Tuple[EnvParameter, ...]]:
    """Normalize the ``parameters=`` of one builder and check it against its
    templates.

    The source builders accept three spellings: one parameter, a tuple of
    parameters, or ``None``. They are normalized into the tuple that the link
    stores (``None`` for no parameters at all).

    The check runs in both directions, and a failure fails the builder call:

    - A template slot that no parameter declares leaves the path unresolvable.
      This includes the case in which ``parameters=`` is absent altogether.
    - A parameter that no template spells declares a variable that nothing
      reads.

    Both are spelling mistakes, and the builder call is the right place to
    report them.
    """
    if parameters is None:
        normalized: Tuple[EnvParameter, ...] = ()
    elif isinstance(parameters, EnvParameter):
        normalized = (parameters,)
    elif isinstance(parameters, Sequence):
        normalized = tuple(parameters)
        for parameter in normalized:
            if not isinstance(parameter, EnvParameter):
                raise TypeError(
                    f"{seat} parameters= expects an env_parameter(...) result or a "
                    f"tuple of such results, got {parameter!r}"
                )
    else:
        raise TypeError(
            f"{seat} parameters= expects an env_parameter(...) result or a "
            f"tuple of such results, got {type(parameters).__name__}"
        )
    declared: Dict[str, EnvParameter] = {}
    for parameter in normalized:
        if parameter.slot_name in declared:
            raise TypeError(
                f"{seat} declares the slot {{{parameter.slot_name}}} in two "
                "parameters. Declare each slot only once"
            )
        declared[parameter.slot_name] = parameter
    spelled = {slot for template in templates for slot in template_slots(template)}
    unknown = sorted(spelled - set(declared))
    if unknown:
        raise TypeError(
            f"{seat} uses the slot(s) {', '.join('{%s}' % s for s in unknown)} "
            "in its template, but no env_parameter declares them. Give each slot "
            "a parameters= entry"
        )
    unused = sorted(set(declared) - spelled)
    if unused:
        raise TypeError(
            f"{seat} declares the parameter(s) {', '.join('{%s}' % s for s in unused)}, "
            "but no slot in the template uses them. Remove them or add their slots to the template"
        )
    return normalized or None


def resolve_templated_path(
    context: SettingsContext,
    configured: Union[str, os.PathLike],
    parameters: Optional[Sequence[EnvParameter]],
    source: str,
) -> str:
    """Return the configured spelling with its slots resolved for this pass.

    A spelling without parameters is returned as given: this is the plain file
    path that every unparameterized link spells. A templated spelling resolves
    each of its slots through the parameter that declares it. The pass resolves
    each variable once and reuses the value for the rest of the pass, and it
    reads the environment anew on every pass.

    A variable that is not set breaks the link: a :class:`UserFacingError` names
    the variable, the template, and the source, unless the parameter declared a
    ``default=``. A value outside the whitelist breaks the link in the same way.
    The resolved value of every freshly resolved variable is written to the log
    as a debug record that names the file that it produced.
    """
    text = os.fspath(configured)
    if not parameters:
        return text
    by_slot = {parameter.slot_name: parameter for parameter in parameters}
    fresh: Dict[str, str] = {}

    def reader(parameter: EnvParameter) -> Callable[[], str]:
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
                    f"the slot {{{slot}}} has no env_parameter declared"
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


def _read_variable(parameter: EnvParameter, template: str, source: str) -> str:
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
                    "its env_parameter declares no default="
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
