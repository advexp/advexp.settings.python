"""A broken storage: corrupt, unreadable, or of the wrong shape.

A file that the parser refuses collects one source error for each required
member, with the own words of the parser in the cause. This holds only while
every member is required. The served default of an optional member must not
hide the broken file, so if one is present, the error of the parser leaves
the load pass unchanged.

A path that cannot be read at all (a directory in the place where the file
should be) collects the OS error in the same way. A JSON file that parses
into an array is refused, in the words of the parser. A dotenv line that
python-dotenv skips is reported as a warning, next to the path of the file.
A save pass over a corrupt file aborts before it writes anything.
"""

import logging

import pytest
import tomlkit
from ruamel.yaml import YAML as _RuamelYAML
from ruamel.yaml.error import YAMLError as _RuamelYAMLError
from settings_broken_storage_classes import (
    BROKEN_LINE_DOTENV_FILE,
    CORRUPT_OPTIONAL_JSON_FILE,
    CORRUPT_OPTIONAL_TOML_FILE,
    CORRUPT_OPTIONAL_YAML_FILE,
    CORRUPT_REQUIRED_JSON_FILE,
    CORRUPT_REQUIRED_TOML_FILE,
    CORRUPT_REQUIRED_YAML_FILE,
    SAVE_INTO_CORRUPT_JSON_FILE,
    SAVE_INTO_CORRUPT_TOML_FILE,
    SAVE_INTO_CORRUPT_YAML_FILE,
    TOP_LEVEL_ARRAY_JSON_FILE,
    UNREADABLE_DOTENV_FILE,
    UNREADABLE_JSON_FILE,
    UNREADABLE_TOML_FILE,
    UNREADABLE_YAML_FILE,
    BrokenLineDotenvSettings,
    CorruptOptionalJsonSettings,
    CorruptOptionalTomlSettings,
    CorruptOptionalYamlSettings,
    CorruptRequiredJsonSettings,
    CorruptRequiredTomlSettings,
    CorruptRequiredYamlSettings,
    SaveIntoCorruptJsonSettings,
    SaveIntoCorruptTomlSettings,
    SaveIntoCorruptYamlSettings,
    TopLevelArrayJsonSettings,
    UnreadableDotenvSettings,
    UnreadableJsonSettings,
    UnreadableTomlSettings,
    UnreadableYamlSettings,
)
from settings_storage_paths import prepare_storage_dir
from tomlkit.exceptions import ParseError

from advexp.settings import (
    AggregateLoadError,
    MemberLoadError,
    MissingValueError,
    SourceLoadError,
)

# the parser detail of the corrupt inputs: the JSON module's own wording for
# "{not json", the TOML parser's for "[not toml". The JSON module is the
# standard library's, so its wording is stable; tomlkit words its errors as
# its releases see fit (0.15.2 moved the column of this one), so the detail
# comes from the installed parser itself — the library's contract is to
# carry the parser's words, whatever they currently are
JSON_PARSER_DETAIL = "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"
try:
    tomlkit.parse("[not toml")
except ParseError as _toml_parse_error:
    TOML_PARSER_DETAIL = str(_toml_parse_error)
try:
    _RuamelYAML(typ="rt").load("{not yaml")
except _RuamelYAMLError as _yaml_parse_error:
    YAML_PARSER_DETAIL = str(_yaml_parse_error)


# ---------------------------------------------------------------------------
# A corrupt storage of required members: one source error per member
# ---------------------------------------------------------------------------


def test_corrupt_storage_required_members_json():
    """``{not json`` with required members only."""
    prepare_storage_dir()
    CORRUPT_REQUIRED_JSON_FILE.write_text("{not json", encoding="utf-8")

    with pytest.raises(AggregateLoadError) as info:
        CorruptRequiredJsonSettings.load_settings()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the JSON file {CORRUPT_REQUIRED_JSON_FILE}) "
        "of 'CorruptRequiredJsonSettings' is required: the JSON file raised ValueError "
        f"(advexp.settings: cannot parse the JSON settings file {CORRUPT_REQUIRED_JSON_FILE}: "
        f"{JSON_PARSER_DETAIL})"
    )
    assert isinstance(error.__cause__, ValueError)
    assert str(error.__cause__) == (
        f"advexp.settings: cannot parse the JSON settings file {CORRUPT_REQUIRED_JSON_FILE}: "
        f"{JSON_PARSER_DETAIL}"
    )


def test_corrupt_storage_required_members_toml():
    """``[not toml`` with required members only."""
    prepare_storage_dir()
    CORRUPT_REQUIRED_TOML_FILE.write_text("[not toml", encoding="utf-8")

    with pytest.raises(AggregateLoadError) as info:
        CorruptRequiredTomlSettings.load_settings()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the TOML file {CORRUPT_REQUIRED_TOML_FILE}) "
        "of 'CorruptRequiredTomlSettings' is required: the TOML file raised ValueError "
        f"(advexp.settings: cannot parse the TOML settings file {CORRUPT_REQUIRED_TOML_FILE}: "
        f"{TOML_PARSER_DETAIL})"
    )
    assert isinstance(error.__cause__, ValueError)
    assert str(error.__cause__) == (
        f"advexp.settings: cannot parse the TOML settings file {CORRUPT_REQUIRED_TOML_FILE}: "
        f"{TOML_PARSER_DETAIL}"
    )


def test_corrupt_storage_required_members_yaml():
    """``{not yaml`` with required members only."""
    prepare_storage_dir()
    CORRUPT_REQUIRED_YAML_FILE.write_text("{not yaml", encoding="utf-8")

    with pytest.raises(AggregateLoadError) as info:
        CorruptRequiredYamlSettings.load_settings()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the YAML file {CORRUPT_REQUIRED_YAML_FILE}) "
        "of 'CorruptRequiredYamlSettings' is required: the YAML file raised ValueError "
        f"(advexp.settings: cannot parse the YAML settings file {CORRUPT_REQUIRED_YAML_FILE}: "
        f"{YAML_PARSER_DETAIL})"
    )
    assert isinstance(error.__cause__, ValueError)
    assert str(error.__cause__) == (
        f"advexp.settings: cannot parse the YAML settings file {CORRUPT_REQUIRED_YAML_FILE}: "
        f"{YAML_PARSER_DETAIL}"
    )


# ---------------------------------------------------------------------------
# A corrupt storage with an optional member: the parser's error re-raised
# ---------------------------------------------------------------------------


def test_corrupt_storage_with_an_optional_member_json():
    """A served default must not mask a corrupt file."""
    prepare_storage_dir()
    CORRUPT_OPTIONAL_JSON_FILE.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        CorruptOptionalJsonSettings.load_settings()

    assert str(info.value) == (
        f"advexp.settings: cannot parse the JSON settings file {CORRUPT_OPTIONAL_JSON_FILE}: "
        f"{JSON_PARSER_DETAIL}"
    )


def test_corrupt_storage_with_an_optional_member_toml():
    """A served default must not mask a corrupt file."""
    prepare_storage_dir()
    CORRUPT_OPTIONAL_TOML_FILE.write_text("[not toml", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        CorruptOptionalTomlSettings.load_settings()

    assert str(info.value) == (
        f"advexp.settings: cannot parse the TOML settings file {CORRUPT_OPTIONAL_TOML_FILE}: "
        f"{TOML_PARSER_DETAIL}"
    )


def test_corrupt_storage_with_an_optional_member_yaml():
    """A served default must not mask a corrupt file."""
    prepare_storage_dir()
    CORRUPT_OPTIONAL_YAML_FILE.write_text("{not yaml", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        CorruptOptionalYamlSettings.load_settings()

    assert str(info.value) == (
        f"advexp.settings: cannot parse the YAML settings file {CORRUPT_OPTIONAL_YAML_FILE}: "
        f"{YAML_PARSER_DETAIL}"
    )


# ---------------------------------------------------------------------------
# An unreadable storage: the path is a directory
# ---------------------------------------------------------------------------


def test_unreadable_storage_dotenv():
    """The dotenv path is a directory, so every open fails."""
    prepare_storage_dir()
    if UNREADABLE_DOTENV_FILE.is_dir():
        UNREADABLE_DOTENV_FILE.rmdir()  # a leftover directory from an earlier run
    UNREADABLE_DOTENV_FILE.mkdir()

    with pytest.raises(AggregateLoadError) as info:
        UnreadableDotenvSettings.load_settings()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{UNREADABLE_DOTENV_FILE}) of 'UnreadableDotenvSettings' is required: "
        f"the dotenv file raised IsADirectoryError ([Errno 21] Is a directory: "
        f"'{UNREADABLE_DOTENV_FILE}')"
    )
    assert isinstance(error.__cause__, OSError)


def test_unreadable_storage_json():
    """The JSON path is a directory, so every open fails."""
    prepare_storage_dir()
    if UNREADABLE_JSON_FILE.is_dir():
        UNREADABLE_JSON_FILE.rmdir()  # a leftover directory from an earlier run
    UNREADABLE_JSON_FILE.mkdir()

    with pytest.raises(AggregateLoadError) as info:
        UnreadableJsonSettings.load_settings()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the JSON file {UNREADABLE_JSON_FILE}) "
        "of 'UnreadableJsonSettings' is required: "
        f"the JSON file raised IsADirectoryError "
        f"([Errno 21] Is a directory: '{UNREADABLE_JSON_FILE}')"
    )
    assert isinstance(error.__cause__, OSError)


def test_unreadable_storage_toml():
    """The TOML path is a directory, so every open fails."""
    prepare_storage_dir()
    if UNREADABLE_TOML_FILE.is_dir():
        UNREADABLE_TOML_FILE.rmdir()  # a leftover directory from an earlier run
    UNREADABLE_TOML_FILE.mkdir()

    with pytest.raises(AggregateLoadError) as info:
        UnreadableTomlSettings.load_settings()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the TOML file {UNREADABLE_TOML_FILE}) "
        "of 'UnreadableTomlSettings' is required: "
        f"the TOML file raised IsADirectoryError "
        f"([Errno 21] Is a directory: '{UNREADABLE_TOML_FILE}')"
    )
    assert isinstance(error.__cause__, OSError)


def test_unreadable_storage_yaml():
    """The YAML path is a directory, so every open fails."""
    prepare_storage_dir()
    if UNREADABLE_YAML_FILE.is_dir():
        UNREADABLE_YAML_FILE.rmdir()  # a leftover directory from an earlier run
    UNREADABLE_YAML_FILE.mkdir()

    with pytest.raises(AggregateLoadError) as info:
        UnreadableYamlSettings.load_settings()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"setting 'answer' (key 'answer' in the YAML file {UNREADABLE_YAML_FILE}) "
        "of 'UnreadableYamlSettings' is required: "
        f"the YAML file raised IsADirectoryError "
        f"([Errno 21] Is a directory: '{UNREADABLE_YAML_FILE}')"
    )
    assert isinstance(error.__cause__, OSError)


# ---------------------------------------------------------------------------
# The wrong shape: a JSON array where the settings object should be
# ---------------------------------------------------------------------------


def test_json_array_at_the_top_level_is_refused():
    """The file parses, but the document is not an object."""
    prepare_storage_dir()
    TOP_LEVEL_ARRAY_JSON_FILE.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        TopLevelArrayJsonSettings.load_settings()

    assert str(info.value) == (
        f"JSON settings file {TOP_LEVEL_ARRAY_JSON_FILE} "
        "must contain an object at the top level, got list"
    )


# ---------------------------------------------------------------------------
# The dotenv backend's own corrupt form: a line python-dotenv skips
# ---------------------------------------------------------------------------


def test_dotenv_line_that_cannot_parse_warns_and_misses(caplog):
    """The line is reported beside the file's path, the members it addressed
    miss, and the pass itself does not abort over it."""
    prepare_storage_dir()
    BROKEN_LINE_DOTENV_FILE.write_text(
        """??? no binding here
EMX_CONTROL=44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.settings"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenLineDotenvSettings.load_settings()

    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass — the class keeps the state it had
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BrokenLineDotenvSettings.control
    (error,) = info.value.errors
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        f"setting 'answer' (environment variable 'EMX_ANSWER' in the dotenv file "
        f"{BROKEN_LINE_DOTENV_FILE}) of 'BrokenLineDotenvSettings' is required: "
        "the dotenv file provided no value"
    )
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"the dotenv file {BROKEN_LINE_DOTENV_FILE}: "
        "python-dotenv could not parse statement starting at line 1"
    ) in warning_messages


# ---------------------------------------------------------------------------
# The save pass over a corrupt file
# ---------------------------------------------------------------------------


def test_save_into_a_corrupt_file_json():
    """The save pass reads the file first, so a corrupt file aborts the save
    and nothing is written over it."""
    prepare_storage_dir()
    SAVE_INTO_CORRUPT_JSON_FILE.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        SaveIntoCorruptJsonSettings.save_settings()

    assert str(info.value) == (
        f"advexp.settings: cannot parse the JSON settings file {SAVE_INTO_CORRUPT_JSON_FILE}: "
        f"{JSON_PARSER_DETAIL}"
    )
    # the pass wrote nothing over the file it could not read
    assert SAVE_INTO_CORRUPT_JSON_FILE.read_text(encoding="utf-8") == "{not json"


def test_save_into_a_corrupt_file_toml():
    """The save pass reads the file first, so a corrupt file aborts the save
    and nothing is written over it."""
    prepare_storage_dir()
    SAVE_INTO_CORRUPT_TOML_FILE.write_text("[not toml", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        SaveIntoCorruptTomlSettings.save_settings()

    assert str(info.value) == (
        f"advexp.settings: cannot parse the TOML settings file {SAVE_INTO_CORRUPT_TOML_FILE}: "
        f"{TOML_PARSER_DETAIL}"
    )
    assert SAVE_INTO_CORRUPT_TOML_FILE.read_text(encoding="utf-8") == "[not toml"


def test_save_into_a_corrupt_file_yaml():
    """The save pass reads the file first, so a corrupt file aborts the save
    and nothing is written over it."""
    prepare_storage_dir()
    SAVE_INTO_CORRUPT_YAML_FILE.write_text("{not yaml", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        SaveIntoCorruptYamlSettings.save_settings()

    assert str(info.value) == (
        f"advexp.settings: cannot parse the YAML settings file {SAVE_INTO_CORRUPT_YAML_FILE}: "
        f"{YAML_PARSER_DETAIL}"
    )
    assert SAVE_INTO_CORRUPT_YAML_FILE.read_text(encoding="utf-8") == "{not yaml"
