# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""The source builder of the pydantic family for this distribution.

The link that the builder returns carries a pydantic model into the chain
as a source of its own. The model is either the class, as in
``pydantic_source(AppSettings)``, and every pass constructs it anew, or
one instance, as in ``pydantic_source(AppSettings(port=9000))``, and the
link serves the values that this instance resolved once, at the
declaration. The builder is the chain spelling of the family for the
classes of this distribution: the link that it returns carries the name of
the distribution, and the ``class`` statement of a class of another
distribution rejects it.

The family rides pydantic, which the ``pydantic`` extra declares:
``pip install "advexp-configuration[pydantic]"``. Importing this module
without the extra fails at the import of pydantic itself.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Type, Union

from pydantic import BaseModel

from advexp.configuration.plugin_api import PACKAGE_NAME
from advexp.configuration.plugins.pydantic.serializer import (
    MODEL_CLASS_PARAM,
    MODEL_VALUES_PARAM,
    PydanticSourceSerializer,
    _model_values,
)
from advexp.settings_base.source_binding import SourceBinding
from advexp.settings_base.source_link import SourceLink


def pydantic_source(model: Union[Type[BaseModel], BaseModel]) -> SourceBinding:
    """Declare a pydantic model link: a model that is read as a source.

    Pass the result of the builder to the ``options=`` keyword of the
    ``class`` statement, either alone (for a class whose members all come
    from the model) or inside ``Sources(...)`` as one link of the chain:

    ```python
    class AppConfig(Configuration, options=Sources(
        env_source(name_prefix="APP_"),
        pydantic_source(AppSettings),
    )):
        api_token: str
    ```

    The argument is either the model class or one instance of it:

    - The class form constructs the model on every load. The model resolves
      its own sources anew each time — the environment, a ``.env`` file,
      whatever the model's ``model_config`` declares — and the link serves
      the values of its ``model_dump()``. A model that fails to construct
      is a broken source, like a file that cannot be parsed: the load of
      the member that reached the link fails with the model's validation
      error, and sources below the link never hide it.
    - The instance form serves the values of the one given instance,
      resolved once, here at the declaration. It carries values that the
      class form cannot build itself: constructor arguments, a
      ``secrets_dir=``, a model whose construction has side effects that
      must not repeat.

    In both forms the layer works in the same way as the mapping source.
    It uses member names only, so the class keeps the field names of the
    model as its member names, and an explicit ``name=`` or ``aliases=``
    of a member changes nothing here. A key that names no member is
    dropped, with a debug record. Values go through the common conversion
    pipeline, native types included: a ``timedelta`` field arrives as a
    ``timedelta``, a nested model as a dictionary, which a dataclass
    member of the class accepts. Secret fields (``SecretStr``,
    ``SecretBytes``) the layer unwraps on the way in, so the member of the
    class decides, by its own annotation, whether to wrap the value again.
    Every value that a load finds is served as a fresh copy, and the
    source is never written back.
    """
    params: Dict[str, Any]
    if isinstance(model, BaseModel):
        params = {
            MODEL_CLASS_PARAM: type(model),
            MODEL_VALUES_PARAM: copy.deepcopy(_model_values(model)),
        }
    elif isinstance(model, type) and issubclass(model, BaseModel):
        params = {MODEL_CLASS_PARAM: model}
    else:
        spelled = model.__name__ if isinstance(model, type) else type(model).__name__
        raise TypeError(
            "pydantic_source() expects a pydantic model class, or an instance "
            f"of one, got {spelled}"
        )
    return SourceBinding(
        link=SourceLink(serializer_class=PydanticSourceSerializer, params=params),
        family=PACKAGE_NAME,
    )
