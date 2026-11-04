# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The UTF-8 byte order mark (BOM), shared by the file backends of the family.

A settings file may start with a BOM, which is a habit of some Windows
editors. The JSON backends tolerate it: the load strips it for the parser,
and the backend that stores values writes it back. The TOML backends refuse
it, because TOML requires plain UTF-8, and they name the BOM as the cause of
the refusal. The marker lives in the foundation of the family because the
file backends of both distributions look at the same first bytes of a file.
"""

from __future__ import annotations

UTF8_BOM = "\ufeff"
"""The UTF-8 byte order mark itself."""
