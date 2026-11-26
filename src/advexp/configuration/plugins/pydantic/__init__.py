# Copyright 2026 Alexey Ivakin
# SPDX-License-Identifier: Apache-2.0

"""Pydantic model source: a pydantic model read as a chain link.

Importing this package enables the source; no explicit registration call
is needed. It rides pydantic, which the ``pydantic`` extra declares:

```python
pip install "advexp-configuration[pydantic]"
```

```python
import advexp.configuration as adv_config
from advexp.configuration.plugins.pydantic import pydantic_source

class AppConfig(adv_config.Configuration, options=adv_config.Sources(
    env_source(name_prefix="APP_"),
    pydantic_source(AppSettings),
)):
    api_token: str
```

``pydantic_source(...)`` returns the result of the builder, which is meant
for the ``options=`` keyword of the ``class`` statement. Assigning the
underlying attribute instance is not the way to use this family, and no
member factory exists, because the model's dictionary uses member names,
which plain declarations already are. As a source, the model is read-only:
it is never written back.

The argument names the model in one of two forms. The class form,
``pydantic_source(AppSettings)``, constructs the model on every load, so
the model keeps resolving its own sources — the environment, a ``.env``
file — as long as it lives in the chain. The instance form,
``pydantic_source(AppSettings(port=9000))``, freezes the values of the one
given instance at the declaration.
"""

from advexp.configuration.plugins.pydantic.options import pydantic_source
from advexp.configuration.plugins.pydantic.serializer import PydanticSourceSerializer

__all__ = [
    "PydanticSourceSerializer",
    "pydantic_source",
]
