"""
Regenera `app/core/proxy_ranges.py`: os intervalos de IP dos proxies que ficam
entre o cliente e o Cloud Run e que `deps.client_ip` pula ao ler o
X-Forwarded-For.

- Google: `goog.json` (todos os IPs do Google) menos `cloud.json` (IPs que
  clientes do Google Cloud alugam). Cobre o front-end do Cloud Run e os proxies
  do Firebase Hosting. A subtração importa: sem ela, quem chamasse o `.run.app`
  de uma VM no GCP com X-Forwarded-For forjado seria tratado como proxy e
  escolheria o próprio "IP" da cota.
- Fastly: a CDN do Firebase Hosting clássico (`x-served-by: cache-…`). Se ela
  aparecer na cadeia, o laço não pode parar nela, senão a cota volta a ser
  dividida por ponto de presença.

    python scripts/update_proxy_ranges.py
"""

from __future__ import annotations

import ipaddress
import json
import urllib.request
from pathlib import Path

GOOG_URL = "https://www.gstatic.com/ipranges/goog.json"
CLOUD_URL = "https://www.gstatic.com/ipranges/cloud.json"
FASTLY_URL = "https://api.fastly.com/public-ip-list"
OUT = Path(__file__).resolve().parent.parent / "app" / "core" / "proxy_ranges.py"

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _load(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (URLs fixas)
        return json.load(resp)


def _networks(data: dict) -> list[Network]:
    return [
        ipaddress.ip_network(p.get("ipv4Prefix") or p.get("ipv6Prefix")) for p in data["prefixes"]
    ]


def google_service_networks(goog: list[Network], cloud: list[Network]) -> list[Network]:
    """`goog` menos `cloud`."""
    out: list[Network] = []
    for net in goog:
        parts = [net]
        for cnet in cloud:
            if cnet.version != net.version:
                continue
            nxt: list[Network] = []
            for part in parts:
                if not part.overlaps(cnet):
                    nxt.append(part)
                elif not cnet.supernet_of(part):
                    nxt.extend(part.address_exclude(cnet))  # type: ignore[arg-type]
            parts = nxt
        out.extend(parts)
    return out


def _collapse(nets: list[Network]) -> list[Network]:
    v4 = ipaddress.collapse_addresses(n for n in nets if n.version == 4)
    v6 = ipaddress.collapse_addresses(n for n in nets if n.version == 6)
    return [*v4, *v6]


def main() -> None:
    goog, cloud, fastly = _load(GOOG_URL), _load(CLOUD_URL), _load(FASTLY_URL)
    google = _collapse(google_service_networks(_networks(goog), _networks(cloud)))
    fastly_nets = _collapse(
        [ipaddress.ip_network(p) for p in fastly["addresses"] + fastly["ipv6_addresses"]]
    )

    def block(nets: list[Network]) -> str:
        return "\n".join(f'    "{n}",' for n in nets)

    OUT.write_text(
        '"""Gerado por scripts/update_proxy_ranges.py — não edite à mão.\n\n'
        f"Google: goog.json {goog.get('creationTime')} menos cloud.json "
        f"{cloud.get('creationTime')}.\nFastly: public-ip-list.\n"
        "Rode o script de novo de tempos em tempos (os intervalos mudam).\n"
        '"""\n\n'
        f"GOOGLE_SERVICE_NETWORKS: tuple[str, ...] = (\n{block(google)}\n)\n\n"
        f"FASTLY_NETWORKS: tuple[str, ...] = (\n{block(fastly_nets)}\n)\n\n"
        "PROXY_NETWORKS: tuple[str, ...] = GOOGLE_SERVICE_NETWORKS + FASTLY_NETWORKS\n",
        encoding="utf-8",
    )
    print(f"{len(google)} Google + {len(fastly_nets)} Fastly -> {OUT}")


if __name__ == "__main__":
    main()
