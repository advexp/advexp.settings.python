"""Dynamic collections: the settings without a declaration.

The dynamic side is reached through the plugin of the backend. A corrupt
file aborts the own load of the plugin with the error of the parser,
unchanged.

The collection reports its own failures through the plugin:

- A name that the collection does not hold names itself in the error.
- A value that the type of the default cannot take produces a warning, and
  the default is served.
- A save of a name that the collection never took names the fix.
"""

import logging

import pytest
import tomlkit
from settings_dynamic_collections_classes import (
    DYNAMIC_CORRUPT_JSON_FILE,
    DYNAMIC_CORRUPT_TOML_FILE,
    DYNAMIC_NAMES_JSON_FILE,
    DYNAMIC_NAMES_TOML_FILE,
    DynamicCorruptJsonSettings,
    DynamicCorruptTomlSettings,
    DynamicNamesJsonSettings,
    DynamicNamesTomlSettings,
)
from settings_storage_paths import prepare_storage_dir
from tomlkit.exceptions import ParseError

from advexp.settings.plugins.json_dynamic_settings import JSONDynamicSettingsPlugin
from advexp.settings.plugins.toml_dynamic_settings import TOMLDynamicSettingsPlugin

# the parser detail of the corrupt inputs: the stable standard library's
# wording for "{not json", the installed tomlkit's own words for "[not toml"
# (it words its errors as its releases see fit — see test_settings_broken_storage)
JSON_PARSER_DETAIL = "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"
try:
    tomlkit.parse("[not toml")
except ParseError as _toml_parse_error:
    TOML_PARSER_DETAIL = str(_toml_parse_error)


# ---------------------------------------------------------------------------
# A corrupt storage aborts the dynamic rebuild
# ---------------------------------------------------------------------------


def test_corrupt_storage_aborts_the_dynamic_rebuild_json():
    """The plugin's load over a corrupt JSON file."""
    prepare_storage_dir()
    DYNAMIC_CORRUPT_JSON_FILE.write_text("{not json", encoding="utf-8")

    plugin = DynamicCorruptJsonSettings.get_plugin(JSONDynamicSettingsPlugin)

    with pytest.raises(ValueError) as info:
        plugin.load_settings()

    assert str(info.value) == (
        f"advexp.settings: cannot parse the JSON settings file {DYNAMIC_CORRUPT_JSON_FILE}: "
        f"{JSON_PARSER_DETAIL}"
    )


def test_corrupt_storage_aborts_the_dynamic_rebuild_toml():
    """The plugin's load over a corrupt TOML file."""
    prepare_storage_dir()
    DYNAMIC_CORRUPT_TOML_FILE.write_text("[not toml", encoding="utf-8")

    plugin = DynamicCorruptTomlSettings.get_plugin(TOMLDynamicSettingsPlugin)

    with pytest.raises(ValueError) as info:
        plugin.load_settings()

    assert str(info.value) == (
        f"advexp.settings: cannot parse the TOML settings file {DYNAMIC_CORRUPT_TOML_FILE}: "
        f"{TOML_PARSER_DETAIL}"
    )


# ---------------------------------------------------------------------------
# The collection's own names and values report through the plugin
# ---------------------------------------------------------------------------


def test_dynamic_names_and_conversion_json(caplog):
    """A missing name, an unconvertible value, a save of a name never set —
    the JSON collection."""
    prepare_storage_dir()
    if DYNAMIC_NAMES_JSON_FILE.exists():
        DYNAMIC_NAMES_JSON_FILE.unlink()  # the collection starts empty

    plugin = DynamicNamesJsonSettings.get_plugin(JSONDynamicSettingsPlugin)

    # a name the collection does not hold names itself
    with pytest.raises(KeyError, match="no dynamic setting 'missing'"):
        plugin.get_setting("missing")

    # a value the default's type cannot take warns and serves the default
    plugin.set_setting("flag", "abc")
    plugin.save_settings()
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        plugin.load_settings()
        value = plugin.get_setting("flag", default=7)
    assert value == 7
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        "cannot convert the value of dynamic setting 'flag' to the type of its default (invalid "
        "literal for int() with base 10: 'abc'); using the default value"
    ) in warning_messages

    # saving a name the collection never took names the fix
    with pytest.raises(KeyError, match="has no value to save"):
        plugin.save_setting("ghost")


def test_dynamic_names_and_conversion_toml(caplog):
    """A missing name, an unconvertible value, a save of a name never set —
    the TOML collection."""
    prepare_storage_dir()
    if DYNAMIC_NAMES_TOML_FILE.exists():
        DYNAMIC_NAMES_TOML_FILE.unlink()  # the collection starts empty

    plugin = DynamicNamesTomlSettings.get_plugin(TOMLDynamicSettingsPlugin)

    with pytest.raises(KeyError, match="no dynamic setting 'missing'"):
        plugin.get_setting("missing")

    plugin.set_setting("flag", "abc")
    plugin.save_settings()
    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        plugin.load_settings()
        value = plugin.get_setting("flag", default=7)
    assert value == 7
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        "cannot convert the value of dynamic setting 'flag' to the type of its default (invalid "
        "literal for int() with base 10: 'abc'); using the default value"
    ) in warning_messages

    with pytest.raises(KeyError, match="has no value to save"):
        plugin.save_setting("ghost")
