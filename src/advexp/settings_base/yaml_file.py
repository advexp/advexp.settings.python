# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The vocabulary of the file bindings of the YAML backends.

A YAML file backend ships in two distributions. One of them loads and stores
settings, and the other reads the same file as a configuration source. Both
share this registry, so the vocabulary lives here, in the foundation of the
family, next to the JSON and dotenv file bindings: one metadata key per
file, and one validator for each. The backends import them from this module.
Registering a key twice hands the registry the same validator, which is a
no-op, while two separately written validators that claim one key would be a
conflict that the registry refuses.

Each binding is class metadata under its key, and it is declared through the
``options=`` keyword of the ``class`` statement. A class that keeps its
variables in a file of its own names the file once, next to the entries of
the other families.

- The static binding names the file of the declared members of the class
  (the extension is not checked: any path works). A class without one uses
  the module default of the backend.
- The dynamic binding names a separate file for the runtime-named entries of
  the class (the settings whose names appear at run time, not as declared
  members). A class without one keeps them in the static file.

Each entry is stored **per declaring class**. A subclass without its own
binding inherits the nearest one above it. A subclass with its own binding
switches to it for itself and its subclasses only, and the base class keeps
reading its own file.

The distributions spell the bindings on their source builders,
``yaml_source(file=..., dynamic_file=...)``, and this module is the storage in
which the builders put them. The static file also has a spelling of its own
next to the source builder: :func:`yaml_file`. It is meant for classes whose
binding is held by another family. The entry names the file of the YAML
members of the class, without binding the class to the YAML storage.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Union

from advexp.settings_base.library_configuration import LibraryConfiguration

YAML_FILE_METADATA = "__YAMLSettingsFile"
"""The class metadata key of the static file binding — one key for both
YAML backends of the family. The value is the file path itself (``str``
or ``os.PathLike``); declaring it binds the class to a file of its own,
and the binding wins over the backend's module default."""

YAML_DYNAMIC_FILE_METADATA = "__YAMLDynamicSettingsFile"
"""The class metadata key of the dynamic entries' own file. The value is
the file path itself; declaring it moves the class's runtime-named entries
into that file, apart from the declared members' one, and the binding wins
over the backend's module default. A class without the binding keeps the
runtime-named entries in the static file."""


def check_yaml_file(value: Any) -> Optional[str]:
    """Describe why ``value`` is not a valid file binding; return ``None`` if it is
    valid.

    This is the single validator of both metadata entries: the value must be a
    file path, that is, a non-empty ``str`` or an ``os.PathLike``. Anything else
    (an empty path, ``None``, a mapping) is a problem that the machinery turns
    into an error that names the settings class and the key. To unbind a class,
    remove the entry (``delete_class_metadata``) instead of storing a
    placeholder.
    """
    if isinstance(value, (str, os.PathLike)):
        text = value if isinstance(value, str) else os.fspath(value)
        if text:
            return None
        return f"must be a non-empty file path, got {value!r}"
    return f"must be a file path (str or os.PathLike), got {type(value).__name__}"


def yaml_file(path: Union[str, os.PathLike]) -> Dict[str, Any]:
    """Declare the YAML file of a settings class: the file seat of the family.

    The entry names the file of the YAML members of the class, without binding
    the class to the YAML storage. It serves a class whose binding is held by
    another family: the plain members read the single source of the class, and
    the members that are declared through the factory of the family,
    ``yaml_setting(...)``, read this file. Pass the result of the builder next to
    the source builder in one ``options=`` sequence:

    ```python
        class AppSettings(Settings, options=(
            env_source(name_prefix="APP_", name_case=NameCase.UPPER),
            yaml_file("app-settings.yaml"),
        )):
            mode: str = "production"  # a plain member: one source — env
            retries: int = yaml_setting(name="retries", default=3)
    ```

    A class that is served by the YAML storage alone names its file on the source
    builder, ``yaml_source(file=...)``. That builder binds the class and lets
    plain members read the file. The seat is for the classes described above. A
    seat next to the source builder of its own family fails the ``class``
    statement, whether or not that builder names a file: the pair would name one
    storage twice, and the file of a bound family belongs on the source builder.

    The seat is a metadata entry of the class itself. A subclass without its own
    seat reads the nearest one above it, and a subclass with its own seat
    switches to it for itself and its subclasses only. The base class keeps
    reading its own file. The runtime channel addresses the same entry
    (``set_class_metadata(YAML_FILE_METADATA, ...)``). The path is checked at the
    call, so an invalid value fails before the ``class`` statement.
    """
    problem = check_yaml_file(path)
    if problem is not None:
        raise TypeError(f"invalid YAML file binding: {problem}")
    return {YAML_FILE_METADATA: path}


LibraryConfiguration.register_class_metadata_validator(YAML_FILE_METADATA, check_yaml_file)
LibraryConfiguration.register_class_metadata_validator(YAML_DYNAMIC_FILE_METADATA, check_yaml_file)
