"""Helix-Agent shared utilities: logging, telemetry, errors, version."""

from helix_agent.common.context import (
    get_current_tenant as get_current_tenant,
)
from helix_agent.common.context import (
    get_current_trace_id as get_current_trace_id,
)
from helix_agent.common.context import (
    require_current_tenant as require_current_tenant,
)
from helix_agent.common.context import (
    reset_current_tenant as reset_current_tenant,
)
from helix_agent.common.context import (
    reset_current_trace_id as reset_current_trace_id,
)
from helix_agent.common.context import (
    set_current_tenant as set_current_tenant,
)
from helix_agent.common.context import (
    set_current_trace_id as set_current_trace_id,
)
from helix_agent.common.deadline import (
    CancelledByUserError as CancelledByUserError,
)
from helix_agent.common.deadline import (
    CancelToken as CancelToken,
)
from helix_agent.common.deadline import (
    DeadlineContext as DeadlineContext,
)
from helix_agent.common.deadline import (
    DeadlineExceededError as DeadlineExceededError,
)
from helix_agent.common.deadline import (
    deadline_check as deadline_check,
)
from helix_agent.common.deadline import (
    get_current_deadline as get_current_deadline,
)
from helix_agent.common.deadline import (
    with_deadline as with_deadline,
)

__version__ = "0.0.0"

__all__ = [
    "CancelToken",
    "CancelledByUserError",
    "DeadlineContext",
    "DeadlineExceededError",
    "__version__",
    "deadline_check",
    "get_current_deadline",
    "get_current_tenant",
    "get_current_trace_id",
    "require_current_tenant",
    "reset_current_tenant",
    "reset_current_trace_id",
    "set_current_tenant",
    "set_current_trace_id",
    "with_deadline",
]
