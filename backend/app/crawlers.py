"""Registry of the existing crawler scripts and how to invoke them."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import settings

BRANDS = [
    "acura", "audi", "bmw", "chrysler", "ford", "gmc", "honda", "hyundai",
    "infiniti", "kia", "lexus", "mazda", "nissan", "porsche", "subaru",
    "toyota", "volvo", "vw",
]


@dataclass(frozen=True)
class CrawlerSpec:
    id: str
    name: str
    group: str
    script: Path
    cwd: Path
    python: Path
    column_required: bool = False       # --column must be supplied
    column_allowed: bool = True         # --column can be supplied
    supports_limit: bool = True
    supports_fresh: bool = True
    supports_show: bool = False
    supports_debug: bool = False
    supports_manual_login: bool = False
    fresh_flag: str = "--fresh"
    headed_flag: str | None = None     # generic "show browser" flag name, e.g. --headed
    notes: str = ""

    def build_args(self, params: dict, input_path: Path, output_path: Path) -> list[str]:
        args = [str(self.script), "--input", str(input_path), "--output", str(output_path)]
        column = (params.get("column") or "").strip()
        if column and self.column_allowed:
            args += ["--column", column]
        limit = int(params.get("limit") or 0)
        if limit > 0 and self.supports_limit:
            args += ["--limit", str(limit)]
        if params.get("fresh") and self.supports_fresh:
            args.append(self.fresh_flag)
        if params.get("show") and self.supports_show:
            args.append("--show")
        elif params.get("show") and self.headed_flag:
            args.append(self.headed_flag)
        if params.get("debug") and self.supports_debug:
            args.append("--debug")
        if params.get("manual_login") and self.supports_manual_login:
            args.append("--manual-login")
        return args

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "group": self.group,
            "available": self.script.exists() and self.python.exists(),
            "column_required": self.column_required,
            "column_allowed": self.column_allowed,
            "supports_limit": self.supports_limit,
            "supports_fresh": self.supports_fresh,
            "supports_show": self.supports_show or self.headed_flag is not None,
            "supports_debug": self.supports_debug,
            "supports_manual_login": self.supports_manual_login,
            "notes": self.notes,
        }


def _brand_crawlers() -> list[CrawlerSpec]:
    python = settings.brand_dir / ".venv" / "Scripts" / "python.exe"
    specs = []
    for brand in BRANDS:
        folder = settings.brand_dir / f"scrapper-{brand}"
        specs.append(
            CrawlerSpec(
                id=f"brand-{brand}",
                name=brand.upper() if brand == "vw" else brand.capitalize(),
                group="Brands (OEM Parts)",
                script=folder / f"scrape_{brand}.py",
                cwd=folder,
                python=python,
                column_required=True,
                supports_limit=False,
                supports_show=False,   # always opens a visible Chrome via CDP
                fresh_flag="--start-over",
                notes="Visible Chrome; solve Cloudflare manually when asked.",
            )
        )
    return specs


def _registry() -> dict[str, CrawlerSpec]:
    keystone_py = settings.keystone_dir / ".venv" / "Scripts" / "python.exe"
    carid_py = settings.carid_dir / "venv" / "Scripts" / "python.exe"
    ccc_py = settings.ccc_dir / ".venv" / "Scripts" / "python.exe"
    specs: list[CrawlerSpec] = [
        CrawlerSpec(
            id="ccc",
            name="CCC Workfile (VIN)",
            group="CCC",
            script=settings.ccc_dir / "crawler.py",
            cwd=settings.ccc_dir,
            python=ccc_py,
            column_allowed=False,
            supports_limit=False,
            supports_fresh=False,
            headed_flag="--headed",
            notes="Login via .env; saved auth in playwright/.auth. Tick 'Show browser' (--headed) if login expired.",
        ),
        CrawlerSpec(
            id="keystone",
            name="Keystone Partslink",
            group="Keystone",
            script=settings.keystone_dir / "keystone_crawler.py",
            cwd=settings.keystone_dir,
            python=keystone_py,
            supports_show=True,
            supports_manual_login=True,
            notes="Headless by default; login via .env. Use --show / manual login if blocked.",
        ),
        CrawlerSpec(
            id="keystone-model",
            name="Keystone Find-Model",
            group="Keystone",
            script=settings.keystone_dir / "keystone_model_crawler.py",
            cwd=settings.keystone_dir,
            python=keystone_py,
            column_allowed=False,
            supports_show=True,
            supports_manual_login=True,
        ),
        CrawlerSpec(
            id="carid",
            name="CARiD Parts",
            group="CARiD",
            script=settings.carid_dir / "carid_scraper.py",
            cwd=settings.carid_dir,
            python=carid_py,
            supports_debug=True,
            supports_show=False,       # always visible Chrome via CDP
            fresh_flag="--no-resume",
            notes="Visible Chrome; solve Cloudflare manually when asked.",
        ),
        CrawlerSpec(
            id="carid-interchange",
            name="CARiD Interchange",
            group="CARiD",
            script=settings.carid_dir / "carid_interchange_scraper.py",
            cwd=settings.carid_dir,
            python=carid_py,
            supports_debug=True,
            fresh_flag="--no-resume",
            notes="Visible Chrome; solve Cloudflare manually when asked.",
        ),
        *_brand_crawlers(),
    ]
    return {s.id: s for s in specs}


CRAWLERS: dict[str, CrawlerSpec] = _registry()


def get_crawler(crawler_id: str) -> CrawlerSpec | None:
    return CRAWLERS.get(crawler_id)
