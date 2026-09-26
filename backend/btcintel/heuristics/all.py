"""Import every detector module so its @heuristic registrations run."""

from btcintel.heuristics import (  # noqa: F401
    change,
    cioh,
    coinbase,
    coinjoin,
    crosschain,
    fingerprint,
    patterns,
)
