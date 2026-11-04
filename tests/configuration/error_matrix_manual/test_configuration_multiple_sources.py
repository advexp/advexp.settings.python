"""Several sources on one class: each source reports in its own words.

One class reads the process environment, a JSON file, a dotenv file, and a
TOML file. The scenario breaks each source in its own way: a missing
variable, a value that cannot be converted, and two empty files. The TOML
source serves its member. A single run therefore shows the aggregate error
carrying the wording of every source, next to a healthy load.
"""

import pytest
from configuration_multiple_sources_classes import (
    MULTI_DOTENV_FILE,
    MULTI_JSON_FILE,
    MULTI_TOML_FILE,
    MultiSourceConfiguration,
)
from configuration_storage_paths import prepare_storage_dir

from advexp.configuration import AggregateLoadError, MemberLoadError


def test_several_sources_report_each_in_its_own_words(monkeypatch):
    """One aggregate, four sources, a different failure on each."""
    prepare_storage_dir()
    monkeypatch.delenv("EMC_ENV_ANSWER", raising=False)
    monkeypatch.setenv("EMC_ENV_KNOWN", "abc")  # the env source: an unconvertible value
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
        MultiSourceConfiguration.load_configuration()

    # the env source reports its missing required variable
    (error,) = info.value.errors
    assert str(error) == (
        "member 'env_answer' (environment variable 'EMC_ENV_ANSWER') "
        "of 'MultiSourceConfiguration' is required: "
        "the process environment provided no value"
    )

    # the env source's unconvertible value fell back to its default
    (fallback,) = info.value.fallbacks
    assert str(fallback) == (
        "member 'env_known' (environment variable 'EMC_ENV_KNOWN') "
        "of 'MultiSourceConfiguration' fell back to its default: "
        "cannot convert 'abc' to int (invalid literal for int() with base 10: 'abc')"
    )

    # the empty files report as the misses of their optional members
    assert [str(miss) for miss in info.value.misses] == [
        f"member 'json_plain' (key 'json_plain' in the JSON file {MULTI_JSON_FILE}) "
        "of 'MultiSourceConfiguration': the JSON file provided no value",
        f"member 'dotenv_extra' (environment variable 'EMC_DOTENV_EXTRA' "
        f"in the dotenv file {MULTI_DOTENV_FILE}) of 'MultiSourceConfiguration': "
        "the dotenv file provided no value",
    ]

    # the abort leaves the class as the call found it: what every source
    # served rides with the failed pass, nothing is applied
    with pytest.raises(MemberLoadError, match="is required"):
        _ = MultiSourceConfiguration.toml_control
    assert MultiSourceConfiguration.json_plain is None
    assert MultiSourceConfiguration.env_known == 7
    assert MultiSourceConfiguration.dotenv_extra == 5
