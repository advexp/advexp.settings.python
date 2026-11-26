# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The member classes of the source families that both distributions share.

Every family with member factories in both distributions declares its members
through one family-wide class: the packages route a member to the family's
source by the member's class alone, so the class must be one physical object
for ``isinstance`` to see the same family in either package. The source links
of the packages name these classes as the family they serve, and each link
carries the serializer of its own package, so a member never learns which
package read it.

The classes belong to no distribution: they spell no ``FAMILY_NAME``, cross
no distribution boundary, and live in every context that declares members —
a class body of either package or a declaration base
(:class:`~advexp.settings_base.setting_declarations.SettingDeclarations`).
The factories of the same modules
(:func:`~advexp.settings_base.json_setting.json_setting` and its siblings)
are their type-checker-friendly spellings.

Nothing here is registered in the serializer registry of
:class:`~advexp.settings_base.library_configuration.LibraryConfiguration`:
the registry is one per process and serves both packages, and one class
cannot carry the serializers of two distributions. The routing of a family
member goes through the source link of its class, which brings the serializer
of the package that built it.
"""

from advexp.settings_base.dotenv_setting import DotenvSetting
from advexp.settings_base.environment_variable_setting import EnvironmentVariableSetting
from advexp.settings_base.json_setting import JSONSetting
from advexp.settings_base.toml_setting import TOMLSetting
from advexp.settings_base.yaml_setting import YAMLSetting

FAMILY_MEMBER_CLASSES = (
    JSONSetting,
    TOMLSetting,
    YAMLSetting,
    DotenvSetting,
    EnvironmentVariableSetting,
)
"""The member classes of the shared source families, for the checks that ask
whether a member belongs to one of them. A member of one of these classes
reads the source link of that family that its class declares, and the class
statement refuses the member when no such link serves it."""
