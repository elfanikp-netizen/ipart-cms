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

# Brands that have more than one crawl site (multiple scrape_<brand>*.py scripts).
# key = the variant name shown in the UI, value = script filename.
SITE_VARIANTS: dict[str, dict[str, str]] = {
    "volvo": {
        "volvopartscounter": "scrape_volvo.py",
        "volvo.oempartsonline": "scrape_volvo2.py",
    },
    "chrysler": {
        "mymoparparts": "scrape_chrysler.py",
        "moparpartsgiant": "scrape_chrysler2.py",
    },
}


@dataclass(frozen=True)
class SiteVariant:
    key: str
    label: str
    script: str
    input_flag: str | None = "--input"
    output_flag: str = "--output"
    supports_fresh: bool | None = None
    fresh_flag: str | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "script": self.script,
            "supports_fresh": self.supports_fresh,
        }


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
    supports_delay: bool = False
    supports_fresh: bool = True
    supports_show: bool = False
    supports_live_visibility: bool = False
    live_visibility_flag: str | None = None
    supports_debug: bool = False
    supports_manual_login: bool = False
    supports_description: bool = False
    supports_resume: bool = True
    resume_requires_output: bool = True
    description_default: str = ""
    fresh_flag: str = "--fresh"
    headed_flag: str | None = None     # generic "show browser" flag name, e.g. --headed
    sites: tuple[SiteVariant, ...] = ()
    notes: str = ""

    def resolve_script(self, site_key: str | None) -> Path:
        """Pick the script for a site variant (default: the primary script)."""
        variant = self.resolve_site(site_key)
        return self.cwd / variant.script if variant else self.script

    def resolve_site(self, site_key: str | None) -> SiteVariant | None:
        if self.sites:
            key = (site_key or "").strip() or self.sites[0].key
            for variant in self.sites:
                if variant.key == key:
                    return variant
        return None

    def build_args(self, params: dict, input_path: Path, output_path: Path) -> list[str]:
        variant = self.resolve_site(params.get("site"))
        script = self.cwd / variant.script if variant else self.script
        args = [str(script)]
        if variant is None or variant.input_flag is not None:
            args += [variant.input_flag if variant else "--input", str(input_path)]
        else:
            args.append(str(input_path))
        args += [variant.output_flag if variant else "--output", str(output_path)]
        column = (params.get("column") or "").strip()
        if column and self.column_allowed:
            args += ["--column", column]
        description = (params.get("description") or "").strip()
        if description and self.supports_description:
            args += ["--description", description]
        limit = int(params.get("limit") or 0)
        if limit > 0 and self.supports_limit:
            args += ["--limit", str(limit)]
        delay = params.get("delay")
        if delay is not None and self.id == "pacific-best":
            args += ["--delay", str(float(delay))]
        supports_fresh = variant.supports_fresh if variant and variant.supports_fresh is not None else self.supports_fresh
        if params.get("fresh") and supports_fresh:
            args.append((variant.fresh_flag if variant else None) or self.fresh_flag)
        if params.get("show") and self.supports_show:
            args.append("--show")
        elif params.get("show") and self.headed_flag:
            args.append(self.headed_flag)
        if params.get("debug") and self.supports_debug:
            args.append("--debug")
        if params.get("manual_login") and self.supports_manual_login:
            args.append("--manual-login")
        if params.get("resume") and self.id == "ccc":
            args.append("--resume")
        if params.get("resume") and self.id == "pacific-best":
            args.append("--resume")
        if self.live_visibility_flag:
            args.append(self.live_visibility_flag)
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
            "supports_delay": self.supports_delay,
            "supports_fresh": self.supports_fresh,
            "supports_show": self.supports_show or self.headed_flag is not None,
            "supports_live_visibility": self.supports_live_visibility,
            "supports_debug": self.supports_debug,
            "supports_manual_login": self.supports_manual_login,
            "supports_description": self.supports_description,
            "description_default": self.description_default,
            "sites": [s.to_dict() for s in self.sites],
            "notes": self.notes,
        }


def _brand_crawlers() -> list[CrawlerSpec]:
    python = settings.brand_dir / ".venv" / "Scripts" / "python.exe"
    specs = []
    for brand in BRANDS:
        folder = settings.brand_dir / f"scrapper-{brand}"
        variants = SITE_VARIANTS.get(brand)
        if variants:
            sites = tuple(SiteVariant(key=k, label=k, script=v) for k, v in variants.items())
        else:
            # single-site crawler: one fixed entry so the UI can show it consistently
            sites = (SiteVariant(key=brand, label=f"{brand} (default)", script=f"scrape_{brand}.py"),)
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
                supports_live_visibility=True,
                fresh_flag="--start-over",
                sites=sites,
                notes="Visible Chrome; solve Cloudflare manually when asked.",
            )
        )
    return specs


def _registry() -> dict[str, CrawlerSpec]:
    keystone_py = settings.keystone_dir / ".venv" / "Scripts" / "python.exe"
    carid_py = settings.carid_dir / "venv" / "Scripts" / "python.exe"
    ccc_py = settings.ccc_dir / ".venv" / "Scripts" / "python.exe"
    vins_py = settings.scrapper_vins_dir / ".venv" / "Scripts" / "python.exe"
    pac_py = settings.pac_dir / ".venv" / "Scripts" / "python.exe"
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
            supports_resume=True,
            resume_requires_output=True,
            headed_flag="--headed",
            supports_description=True,
            description_default="A/M: CAPA",
            sites=(SiteVariant(key="cccone", label="cccone.com", script="crawler.py"),),
            notes="CCC credentials come from its .env. Description matching is case-insensitive substring matching; default: A/M: CAPA.",
        ),
        CrawlerSpec(
            id="keystone",
            name="Keystone Partslink",
            group="Keystone",
            script=settings.keystone_dir / "keystone_crawler.py",
            cwd=settings.keystone_dir,
            python=keystone_py,
            supports_show=True,
            supports_live_visibility=True,
            supports_manual_login=True,
            sites=(SiteVariant(key="orderkeystone", label="preview.orderkeystone.com", script="keystone_crawler.py"),),
            notes="Headless by default; login via .env. Use --show / manual login if blocked.",
        ),
        CrawlerSpec(
            id="pacific-best",
            name="Pacific Best Parts",
            group="Pacific Best",
            script=settings.pac_dir / "pacificbest_crawler.py",
            cwd=settings.pac_dir,
            python=pac_py,
            supports_limit=True,
            supports_delay=True,
            supports_fresh=False,
            supports_show=True,
            supports_live_visibility=True,
            live_visibility_flag="--live-visibility",
            supports_manual_login=True,
            supports_resume=True,
            resume_requires_output=True,
            sites=(SiteVariant(key="pacificbest", label="Pacific Best", script="pacificbest_crawler.py"),),
            notes="Pacific Best Parts catalog. Manual login requires a visible browser; credentials are read from the project .env.",
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
            supports_live_visibility=True,
            supports_manual_login=True,
            sites=(SiteVariant(key="orderkeystone", label="preview.orderkeystone.com", script="keystone_model_crawler.py"),),
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
            supports_live_visibility=True,
            fresh_flag="--no-resume",
            sites=(SiteVariant(key="carid", label="carid.com", script="carid_scraper.py"),),
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
            supports_live_visibility=True,
            fresh_flag="--no-resume",
            sites=(SiteVariant(key="carid", label="carid.com", script="carid_interchange_scraper.py"),),
            notes="Visible Chrome; solve Cloudflare manually when asked.",
        ),
        CrawlerSpec(
            id="vin-lookup",
            name="VIN Lookup",
            group="VIN Lookup",
            script=settings.scrapper_vins_dir / "scrapper_vin.py",
            cwd=settings.scrapper_vins_dir,
            python=vins_py,
            supports_limit=True,
            supports_fresh=True,
            fresh_flag="--start-over",
            supports_show=False,
            supports_live_visibility=True,
            resume_requires_output=False,
            sites=(
                SiteVariant(
                    key="vininspect",
                    label="VinInspect",
                    script="scrapper_vin.py",
                    supports_fresh=True,
                    fresh_flag="--start-over",
                ),
                SiteVariant(
                    key="google",
                    label="Google Search",
                    script="vin_crawler.py",
                    input_flag=None,
                    output_flag="-o",
                    supports_fresh=False,
                ),
            ),
            notes="Both sites find a VIN matching Year/Make/Model, not a specific vehicle. Google Search may require solving a CAPTCHA in its browser window.",
        ),
        *_brand_crawlers(),
    ]
    return {s.id: s for s in specs}


CRAWLERS: dict[str, CrawlerSpec] = _registry()


def get_crawler(crawler_id: str) -> CrawlerSpec | None:
    return CRAWLERS.get(crawler_id)
