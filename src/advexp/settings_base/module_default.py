# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Module-declared values over the process-wide parameters of the backends.

A file backend keeps its process-wide defaults as class attributes of its
configuration holder. Each attribute is one storage slot for the whole
process: if two modules write different files to it, they overwrite each
other, and the order of the imports decides which value survives.

A module that needs a default of its own declares one, instead of writing the
slot. Write the call as the value side of the assignment of the parameter, at
the top level of the module that the value addresses (``holder`` below is
the configuration holder of the backend):

```python
holder.file_path = for_this_module(Path("app-settings.json"))
```

The metaclass of the holder intercepts the assignment and stores the value
under the name of the declaring module. Modules with different declarations
therefore coexist. A settings class resolves the parameter through the
declaration of its own module first. If its module declared none, the class
falls back to the attribute of the holder, which is the unchanged process-wide
channel. Bindings per class keep winning over both.

The declaration is an ordinary statement at the module level. It takes effect
during the import of the module that carries it, so a tool that imports the
settings modules, without running the application, can collect every
declaration from the registry in one call
(:func:`declared_module_defaults`). An assignment inside a function body runs
only when the function is called, so it stays a runtime channel that no
import sees. The top level of the module is the declarative place.

The registry is not tied to one backend: every parameter of every holder uses
it. The bundled file backends open their ``file_path`` parameters, and a
custom backend registers its own parameters in the same way
(:func:`register_module_default`). Each declared value passes the validator
that the backend registered next to its parameter.

A parameter is spelled as one attribute read of its holder
(``lambda holder: holder.file_path``), never as a bare string. If an
attribute is renamed, the registration fails loudly, instead of leaving a
dead name behind.
"""

from __future__ import annotations

import sys
from copy import deepcopy
from types import FrameType
from typing import Any, Callable, Dict, Optional, Tuple


class ModuleDefault:
    """The marker that a module declaration carries: the declared value and the
    module to which it belongs.

    Only :func:`for_this_module` builds the marker, and it names the calling
    module at the call. Only the metaclass of the holders consumes the marker,
    at the moment when the assignment executes. The marker never reaches the
    stored state: the metaclass validates the value and hands the registry a
    plain entry that is keyed by the holder, the parameter, and the module. The
    attribute of the holder stays untouched.
    """

    def __init__(self, module: str, value: Any) -> None:
        self.module = module
        self.value = value


class _ParameterProbe:
    """The object on which a parameter lambda is called: its one attribute read
    returns the name of the attribute that was read.
    """

    def __getattr__(self, name: str) -> str:
        return name


def _parameter_name(parameter: Callable[[Any], Any]) -> str:
    """Return the attribute name that the parameter lambda reads: its single
    attribute access, spelled ``lambda holder: holder.<parameter>``.
    """
    name = parameter(_ParameterProbe())
    if isinstance(name, str) and name:
        return name
    raise TypeError(
        "a parameter must be written as a single attribute access on its holder: "
        "lambda holder: holder.<parameter>"
    )


_PARAMETER_VALIDATORS: Dict[Tuple[type, str], Callable[[Any], Optional[str]]] = {}
"""The parameters opened for module declarations: ``(holder, parameter)``
pairs with the validator each declared value passes. The bundled file
backends register their ``file_path`` parameters beside their holders; a
custom backend registers its own the same way, and the metaclass refuses
a marker on a parameter no backend registered."""

_DECLARED_VALUES: Dict[Tuple[type, str, str], Any] = {}
"""The declared values: ``(holder, parameter, module)`` keys over the
values the modules declared. A declaration of the same parameter for the
same module again replaces the value — the assignment semantics."""


def register_module_default(
    holder: type,
    parameter: Callable[[Any], Any],
    validator: Callable[[Any], Optional[str]],
) -> None:
    """Open a parameter of a configuration holder for module declarations.

    A backend calls this function next to its holder, from the module that
    declares the holder itself. The parameter is one attribute read of the holder
    (``lambda holder: holder.file_path``). The registration checks that the
    attribute named by the lambda is one that the holder declares: a renamed
    attribute fails here, at the import of the module of the holder, instead of
    leaving a dead name that no declaration ever finds.

    The validator is the own validator of the parameter: the same one that the
    metadata registry holds for the file binding of the backend. Every declared
    value passes it at the assignment, so an invalid value fails at the line of
    the declaration itself.

    Registering a parameter again with the same validator is a no-op, which is
    the same rule that the metadata registry follows for family keys. A
    different validator that claims a registered parameter is a conflict, and
    the registry refuses it.
    """
    name = _parameter_name(parameter)
    if not hasattr(holder, name):
        raise TypeError(
            f"{holder.__qualname__} has no attribute {name!r}. The parameter "
            "lambda must read an attribute declared by the holder"
        )
    registered = _PARAMETER_VALIDATORS.get((holder, name))
    if registered == validator:
        return
    if registered is not None:
        raise ValueError(
            f"the parameter {holder.__qualname__}.{name} is already registered "
            f"with a different validator"
        )
    _PARAMETER_VALIDATORS[(holder, name)] = validator


def for_this_module(value: Any) -> Any:
    """Declare the value of a parameter for the module in which this call is
    written.

    Write the call in the assignment itself, at the top level of the module:

    ```python
        holder.file_path = for_this_module(Path("app-settings.json"))
    ```

    The function names the calling module at the call, and the metaclass of the
    holder consumes the marker at the moment when the assignment executes, during
    the import of the module. If you wrap the call in a helper of another module,
    it would name that other module instead: the declaration belongs to the
    assignment that it addresses.

    The call is typed as ``Any`` on purpose: the marker can be assigned to every
    parameter that a holder declares, whatever the own type of the parameter is,
    and the runtime validates the value at the line of the assignment.
    """
    try:
        frame: Optional[FrameType] = sys._getframe(1)
    except ValueError:
        frame = None
    module = frame.f_globals.get("__name__") if frame is not None else None
    if not module:
        raise RuntimeError(
            "for_this_module(...) could not determine the calling module's name. "
            "Declare the value at the top level of a module"
        )
    return ModuleDefault(module, value)


def store_module_default(holder: type, name: str, declaration: ModuleDefault) -> None:
    """Validate one module declaration and store it. The metaclass of the holders
    calls this function.

    The parameter must be one that the backend registered. A marker on an
    unknown attribute is a typo, and the line of the declaration fails with an
    error that names the holder and its registered parameters. The value passes
    the validator of the parameter, and a problem also fails the line, before
    anything is stored. Declaring the same parameter again for the same module
    replaces the value, which is the semantics of an assignment.
    """
    validator = _PARAMETER_VALIDATORS.get((holder, name))
    if validator is None:
        parameters = sorted(
            parameter for holder_, parameter in _PARAMETER_VALIDATORS if holder_ is holder
        )
        if parameters:
            raise TypeError(
                f"{holder.__qualname__}.{name} does not accept a module declaration. "
                f"The parameters of the holder are: {', '.join(parameters)}"
            )
        raise TypeError(
            f"{holder.__qualname__}.{name} does not accept a module declaration, because the "
            f"holder {holder.__qualname__} registers no module-declared parameters"
        )
    problem = validator(declaration.value)
    if problem is not None:
        raise TypeError(
            f"invalid module declaration for {holder.__qualname__}.{name} "
            f"of module {declaration.module!r}: {problem}"
        )
    _DECLARED_VALUES[(holder, name, declaration.module)] = declaration.value


def module_default_for(holder: type, parameter: Callable[[Any], Any], module: str) -> Optional[Any]:
    """Return the value that a module declared for the parameter; ``None`` if it
    declared none.

    The parameter is the same attribute read that the registration spelled. This
    is the lookup of the backends: a settings class asks with the name of the
    module in which it is declared, before it reads the attribute of the holder.
    The declaration of the module therefore wins over the process-wide value, and
    it never reaches the classes of other modules.
    """
    return _DECLARED_VALUES.get((holder, _parameter_name(parameter), module))


def declared_module_defaults() -> Dict[Tuple[type, str, str], Any]:
    """Return a snapshot of every module declaration: ``(holder, parameter,
    module)`` keys over the declared values.

    This is the reader for tools that collect the declarations without running
    the application. Importing the settings modules fills the registry, because
    a declaration at the module level executes at import, and one call hands
    everything to the collector. The snapshot is a deep copy: changing it changes
    nothing in the registry.
    """
    return deepcopy(_DECLARED_VALUES)
