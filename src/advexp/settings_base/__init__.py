# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""
Advexp.Settings-Base: the shared machinery of the Advexp.Settings family.

It is the base layer on which the distributions of the family are built: the
settings context, the value conversion, and the attribute/plugin/serializer
machinery. The settings package builds its public API on top of it, and the
configuration package reuses it for read-only configuration.

Applications install the edition that they need (``advexp-settings``) and
use its application API. This package is the own foundation of the family:
apart from the declaration vocabulary below, its modules are imported by the
distributions, not by application code. The declaration vocabulary — the
marker of a declaration base and the family-wide member factories — is the
one thing that application code imports from here, deliberately: it belongs
to no distribution, so that a declaration base names no package. Both
distributions re-export the same objects from their roots, and a class body
may import them from either side.

The API is under development and may change before the first stable
release.
"""

from advexp.settings_base.dotenv_setting import dotenv_setting
from advexp.settings_base.environment_variable_setting import (
    environment_variable_setting,
)
from advexp.settings_base.json_setting import json_setting
from advexp.settings_base.setting import setting
from advexp.settings_base.setting_declarations import SettingDeclarations
from advexp.settings_base.toml_setting import toml_setting
from advexp.settings_base.yaml_setting import yaml_setting

__all__ = [
    "SettingDeclarations",
    "dotenv_setting",
    "environment_variable_setting",
    "json_setting",
    "setting",
    "toml_setting",
    "yaml_setting",
]
