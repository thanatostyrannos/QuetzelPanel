"""Multi-tenancy seams: Customer entity, ownership label, pure scoping."""
from .models import Customer  # noqa: F401
from .scope import CUSTOMER_LABEL, can_see, scope_for, visible_servers  # noqa: F401
from .store import (  # noqa: F401
    CustomerStore,
    InMemoryCustomerStore,
    make_customer_store,
)
