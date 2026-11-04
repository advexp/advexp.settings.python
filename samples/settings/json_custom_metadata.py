"""
Example: a serializer that reads the runtime metadata of its settings class.

Run from the repository root with the package installed
(``pip install advexp-settings``):

    python samples/settings/json_custom_metadata.py

The recipe in one step: ``MyJSONSerializer`` subclasses the bundled
``JSONSettingsSerializer`` and reads the runtime metadata of the settings
class through its context.

- Member metadata (:meth:`~adv_settings.Settings.set_setting_metadata`)
  turns a reaction on for one member, on demand.
- Class metadata (:meth:`~adv_settings.Settings.set_class_metadata`)
  retunes the whole class.

The application reshapes its storage without redeclaring a single
attribute.

There are two reactions, and both are switched at runtime:

- The ``obfuscate`` member metadata stores the value base64-encoded. This is
  the value reaction: ``save`` and ``load`` run around ``super()``.
- The ``runtime_section`` class metadata moves the members without a
  ``path=`` into a named object. This is the placement reaction: an
  override of the ``_setting_segments`` hook of the base serializer.

The pair is registered with
``adv_settings.LibraryConfiguration.register_settings_attribute``. The
registry lookup is exact, and the slot of the stock ``JSONSetting`` is
already taken by the stock serializer (a second claim is a conflict, not an
override). The custom serializer therefore registers under the bare
``MyJSONSetting`` subclass, which is only a slot marker and has no
parameters of its own.

The settings file is written next to this script and removed at startup, so
every run starts from a clean slate. The run ends with the metadata switches
turned on, so the file that is left behind shows the runtime layout and the
obfuscated value, which is what the inspection after the run sees.
"""

import base64
import json
from pathlib import Path
from typing import Any, List, Optional

import advexp.settings as adv_settings
import advexp.settings.plugin_api as api
import advexp.settings.plugins.json_settings as js


class MyJSONSetting(js.JSONSetting):
    """The registry slot of the custom serializer, and nothing else.

    The lookup is exact per attribute class, and the slot of the stock
    ``JSONSetting`` belongs to the stock serializer (registering it under a
    different serializer is rejected as a conflict). ``MyJSONSerializer``
    therefore registers under this bare subclass. The subclass declares no
    parameters: its construction and behavior are those of a plain
    ``JSONSetting``.
    """


def runtime_json_setting(
    *,
    name: Optional[str] = None,
    default: Any = api.NO_DEFAULT,
    path: Optional[str] = None,
) -> Any:
    """Declare a setting on the custom attribute. This is the type-checker-friendly
    spelling.

    It takes the same keyword parameters and builds the same ``MyJSONSetting``
    attribute. A plain function that returns ``Any`` is the only spelling of a
    declaration that static checkers accept. Assigning the attribute instance
    does the same thing at runtime, but the analyzer cannot see that the
    settings metaclass replaces it with a value descriptor, so it reports a type
    mismatch. A backend of your own ships its factory in the same way (see
    ``json_setting``).
    """
    return MyJSONSetting(name=name, default=default, path=path)


class MyJSONSerializer(js.JSONSettingsSerializer):
    """The stock JSON serializer, extended to react to the runtime metadata.

    Members without metadata keep the stock behavior through the ``super()``
    calls. Dynamic entries (``attr=None``) and attributes of a foreign class are
    narrowed to ``None`` in ``attribute_of``, and they keep the base placement
    and the base value form.

    The reactions are keyed by metadata names that this serializer owns:
    ``obfuscate`` (member metadata, the value form) and ``runtime_section``
    (class metadata, the placement). Both are read through the context that the
    pipeline hands over, and the application switches both at runtime.
    """

    def _runtime_section(self, attr: Optional[api.ISettingAttribute]) -> Optional[str]:
        # class metadata names the object that holds the path-less members
        # at runtime; path= keeps its declared place, and foreign attributes
        # (the global override, say) stay with the base placement
        setting = self.attribute_of(attr, MyJSONSetting)
        if setting is None or setting.path is not None:
            return None
        section = self.context.get_class_metadata("runtime_section")
        return section if isinstance(section, str) and section else None

    def _obfuscates(self, attr: Optional[api.ISettingAttribute]) -> bool:
        # member metadata turns the reaction on at runtime. Metadata is
        # keyed by member name, which is attr.bound_name; dynamic entries
        # (attr=None) carry none
        member = None if attr is None else attr.bound_name
        if member is None:
            return False
        return bool(self.context.get_setting_metadata(member, "obfuscate", False))

    def _setting_segments(
        self, setting_name: str, attr: Optional[api.ISettingAttribute]
    ) -> List[str]:
        # _setting_segments is a hook of the parent class: the base
        # serializer calls it from every storage operation to build the
        # key's location. The override is the placement reaction: it nests
        # the path-less keys one level deeper, under the object the
        # metadata names
        runtime_section = self._runtime_section(attr)
        if runtime_section is not None:
            return [runtime_section, setting_name]
        return super()._setting_segments(setting_name, attr)

    def save(
        self,
        setting_name: str,
        attr: Optional[api.ISettingAttribute],
        value: Any,
    ) -> None:
        # the value reaction: an obfuscated member stores base64(json(value)),
        # plain unreadable text at rest, not encryption. The JSON storage
        # form is rendered first, so any round-trip type wraps the same way.
        if self._obfuscates(attr):
            encoded = json.dumps(self.to_json_value(value))
            value = base64.b64encode(encoded.encode("utf-8")).decode("ascii")
        super().save(setting_name, attr, value)

    def load(self, setting_name: str, attr: Optional[api.ISettingAttribute]) -> Any:
        value = super().load(setting_name, attr)
        if value is not api.NOT_FOUND and self._obfuscates(attr):
            value = json.loads(base64.b64decode(value))
        return value


adv_settings.LibraryConfiguration.register_settings_attribute(MyJSONSetting, MyJSONSerializer)


class AppSettings(adv_settings.Settings):
    """Application settings: every member served by the runtime-tuned serializer."""

    # declared through the sample-local factory (the analyzer-clean
    # spelling); assigning a MyJSONSetting instance directly is the
    # same thing at runtime, but the analyzer flags it
    host: str = runtime_json_setting(name="host", default="localhost")
    # path= is a stock parameter and keeps working: the placement reaction leaves
    # the pathed members where they are
    db_host: str = runtime_json_setting(name="host", path="/service/database", default="localhost")
    db_port: int = runtime_json_setting(name="port", path="/service/database", default=5432)
    api_key: str = runtime_json_setting(name="api_key", default="set-at-install")
    # the runtime metadata below turns its reactions on on demand
    user_token: str = runtime_json_setting(name="user_token", default="")


# a real application binds the class to its own configuration location; the
# sample keeps its file next to the code, so it is easy to inspect after a
# run (main() removes it at startup)
SAMPLES_DIR = Path(__file__).resolve().parent
APP_SETTINGS_FILE = SAMPLES_DIR / "metadata-settings.json"


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> None:
    # every run starts from a clean slate
    APP_SETTINGS_FILE.unlink(missing_ok=True)

    # a real app points this at its own configuration location once at startup
    js.JSONSettingsConfiguration.file_path = APP_SETTINGS_FILE

    section("declare once, load anywhere (missing file -> defaults)")
    AppSettings.load_settings()
    print(f"host    = {AppSettings.host!r}")
    print(f"api_key = {AppSettings.api_key!r}")

    section("assign and save (nothing turned on: the stock layout)")
    AppSettings.host = "api.example.com"
    AppSettings.db_host = "db.example.com"
    AppSettings.db_port = 5433
    AppSettings.api_key = "sk-live-9f31c0"
    AppSettings.user_token = "tok-7f31"
    AppSettings.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    print("(the stock layout: keys at the root, members with path= nested, values stored as is)")

    section("runtime metadata retunes the serializer (nothing redeclared)")
    # start from a clean slate: the switches below apply to a file written
    # under them, and the keys of the previous layout would linger in it as
    # foreign data the library does not know how to relocate
    APP_SETTINGS_FILE.unlink(missing_ok=True)
    # member metadata: the obfuscate reaction turns on for one member
    AppSettings.set_setting_metadata("user_token", "obfuscate", True)
    # class metadata: the path-less members move under a runtime-named object
    AppSettings.set_class_metadata("runtime_section", "runtime")
    AppSettings.save_settings()
    print(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
    print('(class metadata moved the members that have no path= under "runtime",')
    print(' including "host" and "api_key"; member metadata obfuscated the token')
    print(" without either switch being declared anywhere)")

    section("reload: every value, the obfuscated one included, comes back")
    AppSettings.reset_settings()
    AppSettings.load_settings()
    print(f"host       = {AppSettings.host!r}  (read back from the runtime section)")
    print(f"user_token = {AppSettings.user_token!r}  (obfuscated by metadata, decoded on load)")
    print(f"db         = {AppSettings.db_host!r}:{AppSettings.db_port}")

    # dropping the metadata (delete_setting_metadata / delete_class_metadata)
    # would return the stock layout; the sample keeps the switches on, so
    # the file left below shows both reactions at work

    section("the stock plugin wiring is untouched")
    plugin = AppSettings.get_plugin(js.JSONSettingsPlugin)
    print(f"plugin = {plugin.plugin_name!r}, bound to {plugin.context.settings_class.__name__}")

    # put the sample data back, so the file left next to this script is filled
    # in and can be inspected after the run (removed at next startup); it is
    # rewritten from scratch with the metadata still on: the runtime layout
    # and the obfuscated token are what the inspection shows
    APP_SETTINGS_FILE.unlink(missing_ok=True)
    AppSettings.save_settings()
    print(f"\nfile left for inspection (runtime section, token obfuscated): {APP_SETTINGS_FILE}")


if __name__ == "__main__":
    main()
