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
its modules are imported by the distributions, not by application code.

The API is under development and may change before the first stable
release.
"""
