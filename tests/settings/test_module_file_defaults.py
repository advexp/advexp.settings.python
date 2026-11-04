"""Module-declared file defaults: ``for_this_module`` over the holders.

The declaration assigns a ``for_this_module(...)`` value to the ``file_path``
parameter of a backend holder, from the top level of a module. The metaclass
of the holder stores the value under the name of the declaring module. The
file resolution of a settings class asks for the declaration of its own
module first, and only then for the attribute of the holder, which is the
process-wide channel.

The tests declare from the test functions of this module. A call inside a
function names the module in which the function lives, in the same way as a
top-level assignment names the module in which it is written, and the
classes that are declared in the same function belong to the same module. A
class of another module is represented by a hand-built module, in the way
that another settings module of an application would be.
"""

from __future__ import annotations

import json
import types
from typing import Iterator

import pytest

from advexp.settings import Settings, declared_module_defaults, for_this_module
from advexp.settings.plugin_api import register_module_default
from advexp.settings.plugins.environment.dotenv import DotenvConfiguration, dotenv_setting
from advexp.settings.plugins.json_dynamic_settings import (
    JSONDynamicSettingsConfiguration,
    JSONDynamicSettingsPlugin,
)
from advexp.settings.plugins.json_settings import (
    JSONSettingsConfiguration,
    json_setting,
    json_source,
)
from advexp.settings.plugins.toml_settings import TOMLSettingsConfiguration, toml_setting
from advexp.settings.plugins.yaml_settings import YAMLSettingsConfiguration, yaml_setting
from advexp.settings_base.json_file import check_json_file
from advexp.settings_base.module_default import _DECLARED_VALUES

_FOREIGN_SOURCE = """
import advexp.settings as adv_settings
import advexp.settings.plugins.json_settings as js


class ForeignSettings(adv_settings.Settings):
    retries: int = js.json_setting(name="retries", default=3)
"""


def _foreign_settings_class() -> type:
    """A settings class of another module: no declaration of ours
    reaches it."""
    module = types.ModuleType("foreign_settings_module")
    exec(_FOREIGN_SOURCE, module.__dict__)
    return module.ForeignSettings


@pytest.fixture(autouse=True)
def no_module_declarations() -> Iterator[None]:
    # the declaration registry is process-wide; one test's declarations
    # never reach the next
    yield
    _DECLARED_VALUES.clear()


# -- the static side -------------------------------------------------------------------


def test_declaration_gives_the_module_its_file(tmp_path, monkeypatch):
    process_file = tmp_path / "process.json"
    module_file = tmp_path / "module.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", process_file)

    JSONSettingsConfiguration.file_path = for_this_module(module_file)

    class ModuleSettings(Settings):
        retries: int = json_setting(name="retries", default=3)

    ModuleSettings.retries = 7
    ModuleSettings.save_settings()

    assert json.loads(module_file.read_text(encoding="utf-8")) == {"retries": 7}
    assert not process_file.exists()


def test_other_modules_keep_the_process_default(tmp_path, monkeypatch):
    process_file = tmp_path / "process.json"
    module_file = tmp_path / "module.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", process_file)

    JSONSettingsConfiguration.file_path = for_this_module(module_file)

    foreign = _foreign_settings_class()
    foreign.retries = 9
    foreign.save_settings()

    assert json.loads(process_file.read_text(encoding="utf-8")) == {"retries": 9}
    assert not module_file.exists()


def test_class_binding_wins_over_the_declaration(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    module_file = tmp_path / "module.json"
    class_file = tmp_path / "class.json"

    JSONSettingsConfiguration.file_path = for_this_module(module_file)

    class BoundSettings(
        Settings,
        options=json_source(file=class_file),
    ):
        retries: int = json_setting(name="retries", default=3)

    BoundSettings.retries = 7
    BoundSettings.save_settings()

    assert json.loads(class_file.read_text(encoding="utf-8")) == {"retries": 7}
    assert not module_file.exists()


def test_repeated_declaration_last_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    first_file = tmp_path / "first.json"
    second_file = tmp_path / "second.json"

    JSONSettingsConfiguration.file_path = for_this_module(first_file)
    JSONSettingsConfiguration.file_path = for_this_module(second_file)

    class LatestSettings(Settings):
        retries: int = json_setting(name="retries", default=3)

    LatestSettings.retries = 7
    LatestSettings.save_settings()

    assert json.loads(second_file.read_text(encoding="utf-8")) == {"retries": 7}
    assert not first_file.exists()


def test_attribute_keeps_the_process_value(tmp_path, monkeypatch):
    process_file = tmp_path / "process.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", process_file)

    JSONSettingsConfiguration.file_path = for_this_module(tmp_path / "module.json")

    assert JSONSettingsConfiguration.file_path == process_file


def test_no_file_message_names_the_module_spelling(monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)

    class UnconfiguredSettings(Settings):
        retries: int = json_setting(name="retries", default=3)

    with pytest.raises(ValueError, match="for_this_module"):
        UnconfiguredSettings.save_settings()


def test_toml_declaration_of_the_module_file(tmp_path, monkeypatch):
    monkeypatch.setattr(TOMLSettingsConfiguration, "file_path", None)
    module_file = tmp_path / "module.toml"

    TOMLSettingsConfiguration.file_path = for_this_module(module_file)

    class ModuleTomlSettings(Settings):
        retries: int = toml_setting(name="retries", default=3)

    ModuleTomlSettings.retries = 7
    ModuleTomlSettings.save_settings()
    ModuleTomlSettings.reset_settings()
    ModuleTomlSettings.load_settings()

    assert ModuleTomlSettings.retries == 7
    assert module_file.exists()


def test_yaml_declaration_of_the_module_file(tmp_path, monkeypatch):
    monkeypatch.setattr(YAMLSettingsConfiguration, "file_path", None)
    module_file = tmp_path / "module.yaml"

    YAMLSettingsConfiguration.file_path = for_this_module(module_file)

    class ModuleYamlSettings(Settings):
        retries: int = yaml_setting(name="retries", default=3)

    ModuleYamlSettings.retries = 7
    ModuleYamlSettings.save_settings()
    ModuleYamlSettings.reset_settings()
    ModuleYamlSettings.load_settings()

    assert ModuleYamlSettings.retries == 7
    assert module_file.exists()


def test_dotenv_declaration_of_the_module_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(DotenvConfiguration, "file_path", ".env")
    module_file = tmp_path / "module.env"

    DotenvConfiguration.file_path = for_this_module(module_file)

    class ModuleDotenvSettings(Settings):
        host: str = dotenv_setting(name="HOST", default="localhost")

    ModuleDotenvSettings.host = "db.example.com"
    ModuleDotenvSettings.save_settings()
    ModuleDotenvSettings.reset_settings()
    ModuleDotenvSettings.load_settings()

    assert ModuleDotenvSettings.host == "db.example.com"
    assert module_file.exists()
    assert not (tmp_path / ".env").exists()


# -- the dynamic side ------------------------------------------------------------------


def test_dynamic_own_file_declared_for_the_module(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", None)
    dynamic_file = tmp_path / "dynamic.json"

    JSONDynamicSettingsConfiguration.file_path = for_this_module(dynamic_file)

    class DynamicSettings(Settings):
        airplane_mode: bool = json_setting(default=False)

    plugin = DynamicSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = json.loads(dynamic_file.read_text(encoding="utf-8"))
    assert document[JSONDynamicSettingsPlugin.DEFAULT_SECTION]


def test_dynamic_entries_share_the_module_declared_static_file(tmp_path, monkeypatch):
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)
    monkeypatch.setattr(JSONDynamicSettingsConfiguration, "file_path", None)
    static_file = tmp_path / "static.json"

    JSONSettingsConfiguration.file_path = for_this_module(static_file)

    class SharedSettings(Settings):
        airplane_mode: bool = json_setting(default=False)

    plugin = SharedSettings.get_plugin(JSONDynamicSettingsPlugin)
    plugin.set_setting("checkbox", True)
    plugin.save_settings()

    document = json.loads(static_file.read_text(encoding="utf-8"))
    assert JSONDynamicSettingsPlugin.DEFAULT_SECTION in document


# -- the registry ----------------------------------------------------------------------


def test_snapshot_hands_over_every_declaration(tmp_path, monkeypatch):
    module_file = tmp_path / "module.json"
    monkeypatch.setattr(JSONSettingsConfiguration, "file_path", None)

    JSONSettingsConfiguration.file_path = for_this_module(module_file)

    snapshot = declared_module_defaults()
    key = (JSONSettingsConfiguration, "file_path", __name__)
    assert snapshot == {key: module_file}

    snapshot.clear()

    assert declared_module_defaults() == {key: module_file}


# -- refused declarations --------------------------------------------------------------


def test_invalid_declaration_fails_the_assignment_line():
    with pytest.raises(TypeError, match="invalid module declaration"):
        JSONSettingsConfiguration.file_path = for_this_module(123)


def test_unknown_parameter_fails_the_assignment_line():
    with pytest.raises(TypeError, match="does not accept a module declaration"):
        JSONSettingsConfiguration.file_patth = for_this_module("x.json")

    assert not hasattr(JSONSettingsConfiguration, "file_patth")


def test_a_renamed_parameter_fails_the_registration_loudly():
    # the parameter is one attribute read of the holder: a lambda naming an
    # attribute the holder does not declare (a rename the lambda missed)
    # fails at the holder's import, not as a silent miss later
    with pytest.raises(TypeError, match="has no attribute"):
        register_module_default(
            JSONSettingsConfiguration,
            lambda configuration: configuration.renamed_path,
            check_json_file,
        )


def test_a_parameter_lambda_must_read_one_attribute():
    with pytest.raises(TypeError, match="single attribute access"):
        register_module_default(
            JSONSettingsConfiguration,
            lambda configuration: 5,
            check_json_file,
        )
