# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The version of the Advexp.Settings distribution."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("advexp-settings")
except PackageNotFoundError:  # running from a source checkout
    __version__ = "0.1.0"

__all__ = ["__version__"]
