"""
Congelamento dos snapshots de OpenAPI por release (o "Eixo 2" — histórico).

Enquanto o eixo de *versão maior* (``/api/v1``, ``/api/v2``) é governado por
``app/api/versions.py`` e o contrato vivo por ``app/api/openapi.py``, este eixo
guarda a **história das releases** de cada versão: a cada bump da release semântica
servida (campo ``version`` do app FastAPI / ``APIVersion.release``), congelamos o
OpenAPI enriquecido daquele momento em ``docs/openapi/{slug}/{release}.json``.

Esses arquivos são uma segunda testemunha do contrato (além do snapshot de
``tests/contract/openapi_snapshot.json``): a referência interativa pode navegar
releases antigas e o CI pode provar que a última release congelada continua
compatível com o código vivo (ver ``tests/contract/test_openapi_release_snapshots.py``).

A saída é **determinística** (``sort_keys=True``, indent 2, sem escapar não-ASCII,
newline final) para que os diffs sejam revisáveis e o modo ``--check`` seja estável.

Uso::

    venv/Scripts/python scripts/freeze_openapi.py            # escreve/atualiza
    venv/Scripts/python scripts/freeze_openapi.py --check    # CI: falha se defasado
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.api import versions as vreg  # noqa: E402
from app.api.openapi import DOCS_OPENAPI_DIR, openapi_for_version  # noqa: E402
from app.main import app  # noqa: E402


def _dump(schema: dict) -> str:
    """Serialização canônica (chaves ordenadas) para diffs legíveis e ``--check`` estável."""
    return json.dumps(schema, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _sort_releases(releases: list[str]) -> list[str]:
    """Ordena releases da mais nova para a mais antiga (semver se disponível)."""
    unique = list(dict.fromkeys(releases))
    try:
        from packaging.version import InvalidVersion, Version

        def key(release: str) -> tuple[int, object]:
            try:
                return (1, Version(release))
            except InvalidVersion:
                return (0, release)

        return sorted(unique, key=key, reverse=True)
    except Exception:  # pragma: no cover - fallback sem packaging
        return sorted(unique, reverse=True)


def _existing_releases(version_dir: Path) -> list[str]:
    """Releases que já têm arquivo congelado em disco (``{release}.json``)."""
    if not version_dir.is_dir():
        return []
    return [p.stem for p in version_dir.glob("*.json") if p.name != "index.json"]


def _build_manifest(slug: str, version_dir: Path, current_release: str) -> dict:
    """Manifesto ``index.json`` mesclando a release atual com as já congeladas."""
    releases = _existing_releases(version_dir)
    releases.append(current_release)
    ordered = _sort_releases(releases)
    return {"slug": slug, "latest": ordered[0], "releases": ordered}


def freeze(*, check: bool = False) -> int:
    """Congela (ou verifica) o OpenAPI de cada versão registrada.

    Em modo ``check`` nada é escrito: verifica que o arquivo em disco da release
    corrente existe e é byte-a-byte idêntico ao que seria gerado — retornando um
    código de saída não-zero (e explicando) se algo estiver ausente ou defasado.
    """
    problems: list[str] = []
    summary: list[str] = []

    for version in vreg.list_versions():
        slug = version.slug
        release = version.release
        version_dir = DOCS_OPENAPI_DIR / slug
        snapshot_path = version_dir / f"{release}.json"

        schema = openapi_for_version(app, slug)
        payload = _dump(schema)

        if check:
            if not snapshot_path.is_file():
                problems.append(
                    f"[{slug}] snapshot ausente: {snapshot_path.relative_to(ROOT)} "
                    f"(rode `python scripts/freeze_openapi.py` e commite)."
                )
                continue
            on_disk = snapshot_path.read_text(encoding="utf-8")
            if on_disk != payload:
                problems.append(
                    f"[{slug}] snapshot defasado: {snapshot_path.relative_to(ROOT)} "
                    f"difere do OpenAPI vivo da release {release} "
                    f"(rode `python scripts/freeze_openapi.py` e commite)."
                )
                continue
            summary.append(f"[{slug}] OK {snapshot_path.relative_to(ROOT)} ({len(payload)} bytes)")
        else:
            version_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(payload, encoding="utf-8")
            manifest = _build_manifest(slug, version_dir, release)
            (version_dir / "index.json").write_text(_dump(manifest), encoding="utf-8")
            summary.append(
                f"[{slug}] escrito {snapshot_path.relative_to(ROOT)} ({len(payload)} bytes); "
                f"manifesto latest={manifest['latest']} releases={manifest['releases']}"
            )

    for line in summary:
        print(line)
    if problems:
        print("\nProblemas encontrados:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    if check:
        print("\n--check: todos os snapshots congelados estão atualizados.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verifica (sem escrever) que os snapshots estão atualizados; sai != 0 se defasado.",
    )
    args = parser.parse_args(argv)
    return freeze(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
