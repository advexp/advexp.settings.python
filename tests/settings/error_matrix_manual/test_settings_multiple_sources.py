"""Several sources on one class: each source reports in its own words.

One class reads the process environment, a JSON file, a dotenv file, and a
TOML file. The scenario breaks each source in its own way: a missing
variable, a value that cannot be converted, and two empty files. The TOML
source serves its member. A single run therefore shows the aggregate error
carrying the wording of every source, next to a healthy load.
"""

import pytest
from settings_multiple_sources_classes import (
    MULTI_DOTENV_FILE,
    MULTI_JSON_FILE,
    MULTI_TOML_FILE,
    MultiSourceSettings,
)
from settings_storage_paths import prepare_storage_dir

from advexp.settings import AggregateLoadError, MemberLoadError


def test_several_sources_report_each_in_its_own_words(monkeypatch):
    """One aggregate, four sources, a different failure on each."""
    prepare_storage_dir()
    monkeypatch.delenv("EMX_ENV_ANSWER", raising=False)
    monkeypatch.setenv("EMX_ENV_KNOWN", "abc")  # the env source: an unconvertible value
    # the JSON and dotenv sources stay empty; the TOML source holds its value
    for empty_file in (MULTI_JSON_FILE, MULTI_DOTENV_FILE):
        if empty_file.exists():
            empty_file.unlink()  # these sources must hold nothing at all
    MULTI_TOML_FILE.write_text(
        """toml_control = 44
""",
        encoding="utf-8",
    )

    with pytest.raises(AggregateLoadError) as info:
        MultiSourceSettings.load_settings()

    # the env source reports its missing required variable
    (error,) = info.value.errors
    assert str(error) == (
        "setting 'env_answer' (environment variable 'EMX_ENV_ANSWER') "
        "of 'MultiSourceSettings' is required: "
        "the process environment provided no value"
    )

    # the env source's unconvertible value fell back to its default
    (fallback,) = info.value.fallbacks
    assert str(fallback) == (
        "setting 'env_known' (environment variable 'EMX_ENV_KNOWN') "
        "of 'MultiSourceSettings' fell back to its default: "
        "cannot convert 'abc' to int (invalid literal for int() with base 10: 'abc')"
    )

    # the empty files report as the misses of their optional members
    assert [str(miss) for miss in info.value.misses] == [
        f"setting 'json_plain' (key 'json_plain' in the JSON file {MULTI_JSON_FILE}) "
        "of 'MultiSourceSettings': the JSON file provided no value",
        f"setting 'dotenv_extra' (environment variable 'EMX_DOTENV_EXTRA' "
        f"in the dotenv file {MULTI_DOTENV_FILE}) of 'MultiSourceSettings': "
        "the dotenv file provided no value",
    ]

    # the abort leaves the class as the call found it: what every source
    # served rides with the failed pass, nothing is applied
    with pytest.raises(MemberLoadError, match="is required"):
        _ = MultiSourceSettings.toml_control
    assert MultiSourceSettings.json_plain is None
    assert MultiSourceSettings.env_known == 7
    assert MultiSourceSettings.dotenv_extra == 5
