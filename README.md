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

## Web workbench

    cd web && npm install && npm run build     # production bundle served by the API
    cd ../backend && uv run btcintel serve     # http://127.0.0.1:8765

Development with hot reload: run `uv run btcintel serve` and, in another shell, `cd web && npm run dev`
(http://127.0.0.1:5173, proxies /api to the backend).

- Enter an address to get an **automatic analysis**: a risk verdict with the reasons behind it, where the
  funds came from and went to (exchanges, mixers, sanctioned or ransomware addresses, unspent), the
  co-spend cluster and the wallet fingerprint. It fills in live: labels in seconds, the full report in about
  2–4 minutes on public APIs (under a minute when its transactions are already cached);
  **Go deeper** reruns it with larger budgets (5–10 min) and **Open in graph** shows the traced paths.
  The same report on the command line: `uv run btcintel analyze <address> [--deep] [--json]`.
- Search a txid or `txid:vout` to open it in the graph, or a tag name to find labeled addresses.
- Right-click nodes to expand inputs/outputs, trace, follow peel chains or expand clusters.
- Save investigations as cases; export PNG, graph JSON, flows CSV, a Markdown report or your tags as a GraphSense TagPack.
- Public Esplora APIs are rate-limited (~1 request/s on mempool.space): large traces take minutes. Set
  `BTCINTEL_BACKENDS` to a self-hosted Esplora/mempool instance and `BTCINTEL_PROXY=socks5h://127.0.0.1:9050`
  to route lookups through Tor.

## Docker

    docker compose up -d --build              # http://127.0.0.1:8765
    docker compose run --rm btcintel import-tags ofac
    docker compose run --rm btcintel trace <txid> --hops 3
    docker compose run --rm btcintel analyze <address>

- The port is published on 127.0.0.1 only; the API has no authentication. The container still binds
  0.0.0.0, so its "non-loopback address" warning is expected, and `BTCINTEL_ALLOWED_HOSTS` keeps the
  DNS-rebinding Host check on.
- Data lives in `./data` (bind-mounted), shared with a native install; run one server at a time.
- Put `BTCINTEL_BACKENDS` / `BTCINTEL_PROXY` in `.env`. From inside the container the host is
  `host.docker.internal`, not `127.0.0.1`.
- Update: `git pull && docker compose up -d --build`.

License: Apache-2.0.
