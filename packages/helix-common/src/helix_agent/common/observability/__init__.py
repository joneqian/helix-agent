"""Helix-Agent observability primitives.

Stream A.7 — structured JSON logging.
Stream A.8 — OTel SDK / W3C Trace Context (this batch).
Stream A.9 — Prometheus metrics + CI lint (next batch).
"""

from helix_agent.common.observability.log import (
    ExtrasRedactor as ExtrasRedactor,
)
from helix_agent.common.observability.log import (
    HelixJsonFormatter as HelixJsonFormatter,
)
from helix_agent.common.observability.log import (
    get_logger as get_logger,
)
from helix_agent.common.observability.log import (
    init_logging as init_logging,
)
from helix_agent.common.observability.propagation import (
    TRACEPARENT_HEADER as TRACEPARENT_HEADER,
)
from helix_agent.common.observability.propagation import (
    TRACESTATE_HEADER as TRACESTATE_HEADER,
)
from helix_agent.common.observability.propagation import (
    current_span_id_hex as current_span_id_hex,
)
from helix_agent.common.observability.propagation import (
    current_trace_id_hex as current_trace_id_hex,
)
from helix_agent.common.observability.propagation import (
    extract_context as extract_context,
)
from helix_agent.common.observability.propagation import (
    inject_context as inject_context,
)
from helix_agent.common.observability.tracing import (
    HelixComponent as HelixComponent,
)
from helix_agent.common.observability.tracing import (
    get_tracer as get_tracer,
)
from helix_agent.common.observability.tracing import (
    helix_span as helix_span,
)
from helix_agent.common.observability.tracing import (
    init_tracing as init_tracing,
)

__all__ = [
    "TRACEPARENT_HEADER",
    "TRACESTATE_HEADER",
    "ExtrasRedactor",
    "HelixComponent",
    "HelixJsonFormatter",
    "current_span_id_hex",
    "current_trace_id_hex",
    "extract_context",
    "get_logger",
    "get_tracer",
    "helix_span",
    "init_logging",
    "init_tracing",
    "inject_context",
]
