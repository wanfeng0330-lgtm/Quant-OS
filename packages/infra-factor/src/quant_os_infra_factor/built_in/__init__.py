"""Built-in factor auto-discovery.

Importing this package triggers the @register_factor decorators
in all built-in factor modules, registering them in the global FactorRegistry.
"""

from quant_os_infra_factor.built_in import technical  # noqa: F401
from quant_os_infra_factor.built_in import alpha101  # noqa: F401
from quant_os_infra_factor.built_in import liquidity  # noqa: F401
