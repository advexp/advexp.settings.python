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

This package never writes, so there is no save pass to break here. The write
paths meet the read-only contract, which is pinned by its own category.
"""

import logging

import pytest
from configuration_broken_storage_classes import (
    BROKEN_LINE_DOTENV_FILE,
    CORRUPT_OPTIONAL_JSON_FILE,
    CORRUPT_OPTIONAL_TOML_FILE,
    CORRUPT_OPTIONAL_YAML_FILE,
    CORRUPT_REQUIRED_JSON_FILE,
    CORRUPT_REQUIRED_TOML_FILE,
    CORRUPT_REQUIRED_YAML_FILE,
    TOP_LEVEL_ARRAY_JSON_FILE,
    UNREADABLE_DOTENV_FILE,
    UNREADABLE_JSON_FILE,
    UNREADABLE_TOML_FILE,
    UNREADABLE_YAML_FILE,
    BrokenLineDotenvConfiguration,
    CorruptOptionalJsonConfiguration,
    CorruptOptionalTomlConfiguration,
    CorruptOptionalYamlConfiguration,
    CorruptRequiredJsonConfiguration,
    CorruptRequiredTomlConfiguration,
    CorruptRequiredYamlConfiguration,
    TopLevelArrayJsonConfiguration,
    UnreadableDotenvConfiguration,
    UnreadableJsonConfiguration,
    UnreadableTomlConfiguration,
    UnreadableYamlConfiguration,
)
from configuration_storage_paths import prepare_storage_dir

from advexp.configuration import (
    AggregateLoadError,
    MemberLoadError,
    MissingValueError,
    SourceLoadError,
)

# the parser detail of the corrupt inputs, pinned in full: the JSON module's
# own wording for "{not json", the TOML parser's for "[not toml"; the YAML
# detail comes from the installed parser itself, for ruamel words its
# errors as its releases see fit
JSON_PARSER_DETAIL = "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"
TOML_PARSER_DETAIL = "Expected ']' at the end of a table declaration (at line 1, column 6)"
try:
    from ruamel.yaml import YAML as _RuamelYAML
    from ruamel.yaml.error import YAMLError as _RuamelYAMLError

    _RuamelYAML(typ="safe").load("{not yaml")
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
        CorruptRequiredJsonConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the JSON file {CORRUPT_REQUIRED_JSON_FILE}) "
        "of 'CorruptRequiredJsonConfiguration' is required: the JSON file raised "
        "ValueError (advexp.configuration: cannot parse the JSON configuration file "
        f"{CORRUPT_REQUIRED_JSON_FILE}: {JSON_PARSER_DETAIL})"
    )
    assert isinstance(error.__cause__, ValueError)
    assert str(error.__cause__) == (
        f"advexp.configuration: cannot parse the JSON configuration file "
        f"{CORRUPT_REQUIRED_JSON_FILE}: {JSON_PARSER_DETAIL}"
    )


def test_corrupt_storage_required_members_toml():
    """``[not toml`` with required members only."""
    prepare_storage_dir()
    CORRUPT_REQUIRED_TOML_FILE.write_text("[not toml", encoding="utf-8")

    with pytest.raises(AggregateLoadError) as info:
        CorruptRequiredTomlConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the TOML file {CORRUPT_REQUIRED_TOML_FILE}) "
        "of 'CorruptRequiredTomlConfiguration' is required: the TOML file raised "
        "ValueError (advexp.configuration: cannot parse the TOML configuration file "
        f"{CORRUPT_REQUIRED_TOML_FILE}: {TOML_PARSER_DETAIL})"
    )
    assert isinstance(error.__cause__, ValueError)
    assert str(error.__cause__) == (
        f"advexp.configuration: cannot parse the TOML configuration file "
        f"{CORRUPT_REQUIRED_TOML_FILE}: {TOML_PARSER_DETAIL}"
    )


def test_corrupt_storage_required_members_yaml():
    """``{not yaml`` with required members only."""
    prepare_storage_dir()
    CORRUPT_REQUIRED_YAML_FILE.write_text("{not yaml", encoding="utf-8")

    with pytest.raises(AggregateLoadError) as info:
        CorruptRequiredYamlConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the YAML file {CORRUPT_REQUIRED_YAML_FILE}) "
        "of 'CorruptRequiredYamlConfiguration' is required: the YAML file raised "
        "ValueError (advexp.configuration: cannot parse the YAML configuration file "
        f"{CORRUPT_REQUIRED_YAML_FILE}: {YAML_PARSER_DETAIL})"
    )
    assert isinstance(error.__cause__, ValueError)
    assert str(error.__cause__) == (
        f"advexp.configuration: cannot parse the YAML configuration file "
        f"{CORRUPT_REQUIRED_YAML_FILE}: {YAML_PARSER_DETAIL}"
    )


# ---------------------------------------------------------------------------
# A corrupt storage with an optional member: the parser's error re-raised
# ---------------------------------------------------------------------------


def test_corrupt_storage_with_an_optional_member_json():
    """A served default must not mask a corrupt file."""
    prepare_storage_dir()
    CORRUPT_OPTIONAL_JSON_FILE.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        CorruptOptionalJsonConfiguration.load_configuration()

    assert str(info.value) == (
        f"advexp.configuration: cannot parse the JSON configuration file "
        f"{CORRUPT_OPTIONAL_JSON_FILE}: {JSON_PARSER_DETAIL}"
    )


def test_corrupt_storage_with_an_optional_member_toml():
    """A served default must not mask a corrupt file."""
    prepare_storage_dir()
    CORRUPT_OPTIONAL_TOML_FILE.write_text("[not toml", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        CorruptOptionalTomlConfiguration.load_configuration()

    assert str(info.value) == (
        f"advexp.configuration: cannot parse the TOML configuration file "
        f"{CORRUPT_OPTIONAL_TOML_FILE}: {TOML_PARSER_DETAIL}"
    )


def test_corrupt_storage_with_an_optional_member_yaml():
    """A served default must not mask a corrupt file."""
    prepare_storage_dir()
    CORRUPT_OPTIONAL_YAML_FILE.write_text("{not yaml", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        CorruptOptionalYamlConfiguration.load_configuration()

    assert str(info.value) == (
        f"advexp.configuration: cannot parse the YAML configuration file "
        f"{CORRUPT_OPTIONAL_YAML_FILE}: {YAML_PARSER_DETAIL}"
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
        UnreadableDotenvConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{UNREADABLE_DOTENV_FILE}) of 'UnreadableDotenvConfiguration' is required: "
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
        UnreadableJsonConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the JSON file {UNREADABLE_JSON_FILE}) "
        "of 'UnreadableJsonConfiguration' is required: "
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
        UnreadableTomlConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the TOML file {UNREADABLE_TOML_FILE}) "
        "of 'UnreadableTomlConfiguration' is required: "
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
        UnreadableYamlConfiguration.load_configuration()

    assert len(info.value.errors) == 2
    error = info.value.errors[0]
    assert isinstance(error, SourceLoadError)
    assert str(error) == (
        f"member 'answer' (key 'answer' in the YAML file {UNREADABLE_YAML_FILE}) "
        "of 'UnreadableYamlConfiguration' is required: "
        f"the YAML file raised IsADirectoryError "
        f"([Errno 21] Is a directory: '{UNREADABLE_YAML_FILE}')"
    )
    assert isinstance(error.__cause__, OSError)


# ---------------------------------------------------------------------------
# The wrong shape: a JSON array where the configuration object should be
# ---------------------------------------------------------------------------


def test_json_array_at_the_top_level_is_refused():
    """The file parses, but the document is not an object."""
    prepare_storage_dir()
    TOP_LEVEL_ARRAY_JSON_FILE.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError) as info:
        TopLevelArrayJsonConfiguration.load_configuration()

    assert str(info.value) == (
        f"JSON configuration file {TOP_LEVEL_ARRAY_JSON_FILE} "
        "must contain an object at the top level, got list"
    )


# ---------------------------------------------------------------------------
# The dotenv backend's own corrupt form: a line python-dotenv skips
# ---------------------------------------------------------------------------


def test_dotenv_line_that_cannot_parse_warns_and_misses(caplog):
    """The line is reported next to the path of the file, the members that it
    addressed miss, and the pass itself does not abort because of it.
    """
    prepare_storage_dir()
    BROKEN_LINE_DOTENV_FILE.write_text(
        """??? no binding here
EMC_CONTROL=44
""",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING, logger="advexp.configuration"):
        with pytest.raises(AggregateLoadError) as info:
            BrokenLineDotenvConfiguration.load_configuration()

    # the abort leaves the class untouched: control loaded, but its value
    # rides with the failed pass — the class keeps the state it had
    with pytest.raises(MemberLoadError, match="is required"):
        _ = BrokenLineDotenvConfiguration.control
    (error,) = info.value.errors
    assert isinstance(error, MissingValueError)
    assert str(error) == (
        f"member 'answer' (environment variable 'EMC_ANSWER' in the dotenv file "
        f"{BROKEN_LINE_DOTENV_FILE}) of 'BrokenLineDotenvConfiguration' is required: "
        "the dotenv file provided no value"
    )
    warning_messages = [record.getMessage() for record in caplog.records]
    assert (
        f"the dotenv file {BROKEN_LINE_DOTENV_FILE}: "
        "python-dotenv could not parse statement starting at line 1"
    ) in warning_messages
