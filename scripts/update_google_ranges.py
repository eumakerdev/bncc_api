"""
Regenera `app/core/google_ranges.py`: os intervalos de IP de serviços do Google
(front-end do Cloud Run, proxies do Firebase Hosting) que `deps.client_ip` pula
ao ler o X-Forwarded-For.

Fonte oficial: `goog.json` (todos os IPs do Google) menos `cloud.json` (IPs que
clientes do Google Cloud alugam). A subtração importa: sem ela, quem chamasse o
`.run.app` de uma VM no GCP com X-Forwarded-For forjado seria tratado como proxy
e escolheria o próprio "IP" da cota.

    python scripts/update_google_ranges.py
"""

from __future__ import annotations

import ipaddress
import json
import urllib.request
from pathlib import Path

GOOG_URL = "https://www.gstatic.com/ipranges/goog.json"
CLOUD_URL = "https://www.gstatic.com/ipranges/cloud.json"
OUT = Path(__file__).resolve().parent.parent / "app" / "core" / "google_ranges.py"

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def _load(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (URL fixa do Google)
        return json.load(resp)


def _networks(data: dict) -> list[Network]:
    return [
        ipaddress.ip_network(p.get("ipv4Prefix") or p.get("ipv6Prefix")) for p in data["prefixes"]
    ]


def google_service_networks(goog: list[Network], cloud: list[Network]) -> list[Network]:
    """`goog` menos `cloud`, colapsado."""
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
    v4 = ipaddress.collapse_addresses(n for n in out if n.version == 4)
    v6 = ipaddress.collapse_addresses(n for n in out if n.version == 6)
    return [*v4, *v6]


def main() -> None:
    goog, cloud = _load(GOOG_URL), _load(CLOUD_URL)
    nets = google_service_networks(_networks(goog), _networks(cloud))
    lines = "\n".join(f'    "{n}",' for n in nets)
    OUT.write_text(
        '"""Gerado por scripts/update_google_ranges.py — não edite à mão.\n\n'
        f"goog.json {goog.get('creationTime')} menos cloud.json {cloud.get('creationTime')}.\n"
        "Rode o script de novo de tempos em tempos (o Google muda os intervalos).\n"
        '"""\n\n'
        f"GOOGLE_SERVICE_NETWORKS: tuple[str, ...] = (\n{lines}\n)\n",
        encoding="utf-8",
    )
    print(f"{len(nets)} intervalos -> {OUT}")


if __name__ == "__main__":
    main()
