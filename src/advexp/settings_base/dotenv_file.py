# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The class-to-file binding of the dotenv backends.

A ``.env`` file backend ships in two distributions. One of them loads and
stores settings, and the other reads the same file as a configuration
source. Both share this registry, so the vocabulary of the binding lives
here, in the foundation of the family, next to the naming options: one
metadata key, one validator, and one helper. The two backends import them
from this module. Registering the key twice hands the registry the same
validator, which is a no-op, while two separately written validators that
claim one key would be a conflict that the registry refuses.

The binding is class metadata under the family key, and it is declared
through the ``options=`` keyword of the ``class`` statement. A class that
keeps its variables in a file of its own names the file once, next to the
entries of the other families. A class without a binding uses the module
default of the backend.

The entry is stored **per declaring class**. A subclass without its own
binding inherits the nearest one above it. A subclass with its own binding
switches to it for itself and its subclasses only, and the base class keeps
reading its own file.

The file also has a spelling of its own next to the source builder:
:func:`dotenv_file`. It is meant for classes whose binding is held by
another family. The entry names the file of the dotenv members of the
class, without binding the class to the dotenv storage.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Union

from advexp.settings_base.library_configuration import LibraryConfiguration

DOTENV_FILE_METADATA = "__DotenvFile"
"""The class metadata key of the file binding — one key for both dotenv
backends of the family. The value is the file path itself (``str`` or
``os.PathLike``); declaring it binds the class to a file of its own, and
the binding wins over the backend's module default."""


def check_dotenv_file(value: Any) -> Optional[str]:
    """Describe why ``value`` is not a valid file binding; return ``None`` if it is
    valid.

    This is the single validator of the metadata entry of the family: the value
    must be a file path, that is, a non-empty ``str`` or an ``os.PathLike``.
    Anything else (an empty path, ``None``, a mapping) is a problem that the
    machinery turns into an error that names the settings class and the key. To
    unbind a class, remove the entry (``delete_class_metadata``) instead of
    storing a placeholder.
    """
    if isinstance(value, (str, os.PathLike)):
        text = value if isinstance(value, str) else os.fspath(value)
        if text:
            return None
        return f"must be a non-empty file path, got {value!r}"
    return f"must be a file path (str or os.PathLike), got {type(value).__name__}"


def dotenv_file(path: Union[str, os.PathLike]) -> Dict[str, Any]:
    """Declare the ``.env`` file of a settings class: the file seat of the family.

    The entry names the file of the dotenv members of the class, without
    binding the class to the dotenv storage. It serves a class whose binding is
    held by another family: the plain members read the single source of the
    class, and the members that are declared through the factory of the family,
    ``dotenv_setting(...)``, read this file. The variable names are built by the
    shared dictionary of the environment family, so a class that uses an
    ``env_source(...)`` binding applies its naming to the dotenv members too.
    Pass the result of the builder next to the source builder in one
    ``options=`` sequence:

    ```python
        class AppSettings(Settings, options=(
            env_source(name_prefix="APP_", name_case=NameCase.UPPER),
            dotenv_file("app.env"),
        )):
            mode: str = "production"  # a plain member: one source — env
            flag: bool = dotenv_setting(default=False)  # APP_FLAG
    ```

    A class that is served by the dotenv storage alone names its file on the
    source builder, ``dotenv_source(file=...)``. That builder binds the class
    and lets plain members read the file. The seat is for the classes described
    above. A seat next to the source builder of its own family fails the
    ``class`` statement, whether or not that builder names a file: the pair
    would name one storage twice, and the file of a bound family belongs on the
    source builder.

    The seat is a metadata entry of the class itself. A subclass without its
    own seat reads the nearest one above it, and a subclass with its own seat
    switches to it for itself and its subclasses only. The base class keeps
    reading its own file. The runtime channel addresses the same entry
    (``set_class_metadata(DOTENV_FILE_METADATA, ...)``). The path is checked at
    the call, so an invalid value fails before the ``class`` statement.
    """
    problem = check_dotenv_file(path)
    if problem is not None:
        raise TypeError(f"invalid dotenv file binding: {problem}")
    return {DOTENV_FILE_METADATA: path}


LibraryConfiguration.register_class_metadata_validator(DOTENV_FILE_METADATA, check_dotenv_file)
