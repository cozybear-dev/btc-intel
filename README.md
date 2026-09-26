# btc-intel

Open-source Bitcoin blockchain intelligence: trace stolen or illicit funds, cluster addresses into
entities, screen addresses for risk, and study the techniques used to obfuscate fund flows.

- Knowledge base: [docs/kb/index.md](docs/kb/index.md) · [TTP matrix](docs/kb/ttp-matrix.md)
- Design: [docs/superpowers/specs/2026-09-25-btc-intel-design.md](docs/superpowers/specs/2026-09-25-btc-intel-design.md)

## Quickstart (backend)

    curl -LsSf https://astral.sh/uv/install.sh | sh
    cd backend
    uv sync
    uv run pytest
    uv run btcintel catalog check

License: Apache-2.0.
