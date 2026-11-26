---
summary: One set of member declarations for the settings and the configuration class.
---

# Shared declarations

An application that works with both libraries — Advexp.Settings for its
stored settings and Advexp.Configuration for its read-only configuration —
describes its values one time. A *declaration base* holds the declarations,
and the settings class and the configuration class inherit them together.

```python
from advexp.settings_base import (
    SettingDeclarations,
    json_setting,
    setting,
)


class AppDeclarations(SettingDeclarations):
    retries: int = setting(default=3)
    timeout: int = setting(default=30, ge=retries)
    port: int = json_setting(default=8080)
```

The declaration base is a plain class. It loads nothing, validates nothing,
and serves no values: it only holds the declarations. The classes that
inherit it do all of that, each through the sources of its own package.

```python
import advexp.settings as adv_settings
import advexp.configuration as adv_configuration
import advexp.settings.plugins.json_settings as settings_json
import advexp.configuration.plugins.json_settings as configuration_json
import advexp.configuration.plugins.environment.variables as configuration_env


class AppSettings(
    AppDeclarations,
    adv_settings.Settings,
    options=settings_json.json_source(file="app.json"),
):
    # a member of this class alone
    debug: bool = adv_settings.setting(default=False)


class AppConfig(
    AppDeclarations,
    adv_configuration.Configuration,
    options=adv_configuration.Sources(
        configuration_json.json_source(file="app.json"),
        configuration_env.env_source(),
    ),
):
    """The read-only side: the same declarations through a chain."""
```

`AppSettings` loads the poured members from its JSON file; `AppConfig` reads
the same declarations through its chain — the JSON file first, the
environment after it. One declaration, two libraries, no duplication.

## The declaration vocabulary

The factories that a declaration base holds live in `advexp.settings_base`
and belong to no distribution: `setting`, `sourceless_setting`,
`json_setting`, `toml_setting`, `yaml_setting`, `dotenv_setting`, and
`environment_variable_setting`. A declaration base imports them right from
there. In a class body, `setting` and `sourceless_setting` come from the
root of the package, and each family's factory comes from the package of
that family — the import that enables the backend. The factories are the
same functions in either place, and they work in a class body directly,
beside the plain annotations.

A member without `default=` is required: a source must provide its value, or
the load aborts. This holds everywhere — in a declaration base, in a settings
class, in a configuration class — and it matches the plain annotation, which
declares a required member the same way. An optional member says so
explicitly: `default=None`, or any other value to serve when no source has
one.

The declaration answers *what the value is and from which source family it
reads*; the body of the inheriting class *configures the sources of that
class* — which files, which variables, which order.

## References between members

The members of a declaration base may reference each other: a comparison
bound or a `when=` condition takes the attribute of a sibling member
declared earlier in the base. Every inheriting class receives its own bound
copy of the whole set, and the references follow the copies — the `timeout`
above stays no less than the `retries` of the same class, whatever each
class loads.

A member of the class body may reference a member of the base as well:
`ge=AppDeclarations.retries`. The `class` statement turns such a reference
onto the poured copy of that member — the same object the class binds as its
own.

One combination is refused, with an error that names the member and the way
out: the body overrides a name under a reference. A reference that named the
base's declaration has lost its target to the override, and the class
statement asks for a reference to the body's own member instead.

A plain annotation of the base carries a type and a default only. A
reference needs an attribute object, so `ge=AppDeclarations.member` on a
plainly annotated member is the literal value of that member at the moment
the body runs — a frozen bound, not a live reference. Declare the member
through a factory when the reference has to follow the loaded value.

## The base is a blueprint

The `class` statement pours the declarations of the base into the inheriting
class once, at the moment that class is created. A change to the base after
that reaches nothing: the classes that already exist keep the declarations
they received. To change what a class reads, edit the base before the class
is created — in practice, before the module that declares the class is
imported — or declare the member in the body of the class itself.

The marker decides which bases take part. A plain mixin without the
`SettingDeclarations` marker keeps its silence: its annotations stay
annotations, and the settings classes that inherit it ignore them, exactly
as they always did.

## Where the base cannot go

An attribute printed with a family of its own — a backend attribute that a
plugin author derived from a package's attribute base — does not pour: the
`class` statement of the declaration base refuses it, naming the member.
Declare such a member in the class that reads it, or through the
family-wide factories of `advexp.settings_base`.
