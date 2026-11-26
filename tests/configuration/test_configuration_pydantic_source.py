"""PydanticSource tests: the model link of the chain, in its two forms.

The Q rows of the usage matrix walk through the source as the reader meets
it. This module pins the own contract of the plugin: the two forms of the
builder, the vocabulary that the layer uses, and the failure of a model
that cannot construct.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

import advexp.configuration as adv_config
import advexp.configuration.plugins.environment.variables as env
from advexp.configuration import AggregateLoadError, Configuration, Sources
from advexp.configuration.plugins.pydantic import pydantic_source


class Db(BaseModel):
    # the values differ from DbMember's defaults on purpose: an assertion
    # against the defaults alone would pass with no conversion at all
    host: str = "db.internal"
    port: int = 64000


class App(BaseModel):
    debug: bool = False
    db: Db = Db()


@dataclass
class DbMember:
    host: str = "localhost"
    port: int = 5432


def test_the_builder_refuses_a_non_model():
    with pytest.raises(TypeError, match="expects a pydantic model class"):
        pydantic_source("AppSettings")

    with pytest.raises(
        TypeError, match="expects a pydantic model class, or an instance of one, got int"
    ):
        pydantic_source(42)

    with pytest.raises(
        TypeError, match="expects a pydantic model class, or an instance of one, got dict"
    ):
        pydantic_source(dict)


def test_the_class_form_serves_the_models_values():
    # DbMember sits at module level: a dataclass declared inside the test
    # would leave its annotation unresolvable, and the value would arrive
    # as the raw dictionary
    class C(
        Configuration,
        options=pydantic_source(App),
    ):
        debug: bool = True
        db: DbMember = DbMember()

    C.load_configuration()
    assert C.debug is False
    # the model's values, not the member's defaults: the conversion ran
    assert C.db == DbMember(host="db.internal", port=64000)


def test_the_class_form_constructs_the_model_on_every_load(monkeypatch):
    class M(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="APP_")

        token: str = "none"

    class C(
        Configuration,
        options=pydantic_source(M),
    ):
        token: str = "fallback"

    monkeypatch.setenv("APP_TOKEN", "first")
    C.load_configuration()
    assert C.token == "first"

    monkeypatch.setenv("APP_TOKEN", "second")
    C.load_configuration()
    assert C.token == "second"


def test_the_instance_form_freezes_the_values(monkeypatch):
    monkeypatch.setenv("APP_TOKEN", "first")

    class M(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="APP_")

        token: str = "none"

    class C(
        Configuration,
        options=pydantic_source(M()),
    ):
        token: str = "fallback"

    monkeypatch.setenv("APP_TOKEN", "second")
    C.load_configuration()
    assert C.token == "first"


def test_secret_fields_arrive_unwrapped():
    class M(BaseModel):
        password: SecretStr = SecretStr("hunter2")

    class Plain(
        Configuration,
        options=pydantic_source(M),
    ):
        password: str

    class Wrapped(
        Configuration,
        options=pydantic_source(M),
    ):
        password: adv_config.SecretStr

    Plain.load_configuration()
    Wrapped.load_configuration()
    assert Plain.password == "hunter2"
    assert Wrapped.password.get_secret_value() == "hunter2"


def test_a_model_that_cannot_construct_fails_the_member(monkeypatch):
    monkeypatch.delenv("APP_TOKEN", raising=False)

    class M(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="APP_")

        token: str

    class C(
        Configuration,
        options=pydantic_source(M),
    ):
        token: str

    with pytest.raises(AggregateLoadError, match="cannot construct the pydantic model"):
        C.load_configuration()


def test_a_broken_model_leaves_members_served_above_it_alone(monkeypatch):
    # the construction is lazy: the model is built by the first member that
    # reaches the link, so a member that an earlier link already served
    # loads through a model that would not even construct
    monkeypatch.delenv("APP_TOKEN", raising=False)
    monkeypatch.setenv("APP_PORT", "9000")

    class M(BaseSettings):
        model_config = SettingsConfigDict(env_prefix="APP_")

        token: str

    class C(
        Configuration,
        options=Sources(
            env.env_source(name_prefix="APP_", name_case=env.NameCase.UPPER),
            pydantic_source(M),
        ),
    ):
        port: int = 0

    C.load_configuration()
    assert C.port == 9000


def test_the_layer_speaks_member_names_alone(caplog):
    class M(BaseModel):
        host: str = "model-host"
        foreign: str = "not-a-member"

    class C(
        Configuration,
        options=pydantic_source(M),
    ):
        host: str = adv_config.setting(name="HOST", default="fallback")

    with caplog.at_level(logging.DEBUG, logger="advexp.configuration"):
        C.load_configuration()
    assert C.host == "model-host"
    assert any("does not match any member" in record.getMessage() for record in caplog.records)


def test_sources_above_the_model_win_and_below_lose(monkeypatch):
    monkeypatch.setenv("APP_TOKEN", "from-env")

    # a plain model, so that its own value is fixed: a BaseSettings would
    # resolve the same variable itself, and the two links would agree
    class M(BaseModel):
        token: str = "from-model"

    class Above(
        Configuration,
        options=Sources(
            env.env_source(name_prefix="APP_", name_case=env.NameCase.UPPER),
            pydantic_source(M),
        ),
    ):
        token: str = "fallback"

    class Below(
        Configuration,
        options=Sources(
            pydantic_source(M),
            env.env_source(name_prefix="APP_", name_case=env.NameCase.UPPER),
        ),
    ):
        token: str = "fallback"

    Above.load_configuration()
    Below.load_configuration()
    assert Above.token == "from-env"
    assert Below.token == "from-model"
