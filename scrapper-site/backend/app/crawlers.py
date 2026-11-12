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
BRAND_SITE_DOMAINS: dict[str, dict[str, str]] = {
    "acura": {"acura": "acurapartswarehouse.com"},
    "audi": {"audi": "audipartsgiant.com"},
    "bmw": {"bmw": "getbmwparts.com"},
    "chrysler": {
        "mymoparparts": "mymoparparts.com",
        "moparpartsgiant": "www.moparpartsgiant.com",
    },
    "ford": {"ford": "fordpartsgiant.com"},
    "gmc": {"gmc": "parts.gmparts.com"},
    "honda": {"honda": "honda.oempartsonline.com"},
    "hyundai": {"hyundai": "hyundaipartsdeal.com"},
    "infiniti": {"infiniti": "infinitipartsdeal.com"},
    "kia": {"kia": "kiapartsnow.com"},
    "lexus": {"lexus": "lexuspartsnow.com"},
    "mazda": {"mazda": "mazda.oempartsonline.com"},
    "nissan": {"nissan": "nissanpartsdeal.com"},
    "porsche": {"porsche": "porsche.oempartsonline.com"},
    "subaru": {"subaru": "subarupartsdeal.com"},
    "toyota": {"toyota": "autoparts.toyota.com"},
    "volvo": {
        "volvopartscounter": "www.volvopartscounter.com",
        "volvo.oempartsonline": "volvo.oempartsonline.com",
    },
    "vw": {"vw": "parts.vw.com"},
}


@dataclass(frozen=True)
class InputSpec:
    required_headers: tuple[str, ...] = ()
    header_alternatives: tuple[tuple[str, ...], ...] = ()
    template_headers: tuple[str, ...] = ()
    hint: str = ""
    allow_custom_column: bool = True

    def to_dict(self) -> dict:
        return {
            "required_headers": list(self.required_headers),
            "header_alternatives": [list(group) for group in self.header_alternatives],
            "template_headers": list(self.template_headers or self.required_headers),
            "hint": self.hint,
            "allow_custom_column": self.allow_custom_column,
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
    input_spec: InputSpec | None = None
    output_columns: tuple[str, ...] = ()
    output_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "script": self.script,
            "supports_fresh": self.supports_fresh,
            "input": self.input_spec.to_dict() if self.input_spec else None,
            "output_columns": list(self.output_columns),
            "output_notes": self.output_notes,
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
    supports_resume: bool = False
    resume_requires_output: bool = False
    description_default: str = ""
    fresh_flag: str = "--fresh"
    headed_flag: str | None = None     # generic "show browser" flag name, e.g. --headed
    sites: tuple[SiteVariant, ...] = ()
    notes: str = ""
    input_spec: InputSpec = InputSpec()
    input_mode_scripts: dict[str, str] = field(default_factory=dict)
    output_columns: tuple[str, ...] = ()
    output_notes: str = ""

    def input_for_site(self, site_key: str | None) -> InputSpec:
        variant = self.resolve_site(site_key)
        return variant.input_spec if variant and variant.input_spec else self.input_spec

    def resolve_script(self, site_key: str | None, input_mode: str | None = None) -> Path:
        """Pick the input-mode script or site variant, defaulting to the primary script."""
        if input_mode and input_mode in self.input_mode_scripts:
            return self.cwd / self.input_mode_scripts[input_mode]
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
        script = self.resolve_script(params.get("site"), params.get("input_mode"))
        args = [str(script)]
        if variant is None or variant.input_flag is not None:
            args += [variant.input_flag if variant else "--input", str(input_path)]
        else:
            args.append(str(input_path))
        args += [variant.output_flag if variant else "--output", str(output_path)]
        column = (params.get("resolved_column") or params.get("column") or "").strip()
        if column and self.column_allowed:
            args += ["--column", column]
        description = (params.get("description") or "").strip()
        if description and self.supports_description:
            args += ["--description", description]
        if self.id == "ccc" and params.get("search_action") == "vin_partslink_scenario":
            args += ["--search-action", "vin_partslink_scenario"]
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
            "input": self.input_spec.to_dict(),
            "output_columns": list(self.output_columns),
            "output_notes": self.output_notes,
        }


def _brand_crawlers() -> list[CrawlerSpec]:
    python = settings.brand_dir / ".venv" / "Scripts" / "python.exe"
    specs = []
    for brand in BRANDS:
        folder = settings.brand_dir / f"scrapper-{brand}"
        variants = SITE_VARIANTS.get(brand)
        domains = BRAND_SITE_DOMAINS[brand]
        if variants:
            sites = tuple(
                SiteVariant(key=key, label=f"{key} ({domains[key]})", script=script)
                for key, script in variants.items()
            )
        else:
            # single-site crawler: one fixed entry so the UI can show it consistently
            sites = (
                SiteVariant(
                    key=brand,
                    label=f"{brand} ({domains[brand]})",
                    script=f"scrape_{brand}.py",
                ),
            )
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
                supports_resume=True,
                supports_live_visibility=True,
                fresh_flag="--start-over",
                sites=sites,
                notes="Visible Chrome; solve Cloudflare manually when asked.",
                output_columns=("OEM Number", "MSRP", "Date", "Status"),
                input_spec=InputSpec(
                    header_alternatives=(("OEM Number", "OEM", "Part Number"),),
                    template_headers=("OEM Number",),
                    hint="Put one OEM number per row, then choose its column.",
                ),
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
            name="CCC Workflow",
            group="CCC",
            script=settings.ccc_dir / "crawler.py",
            cwd=settings.ccc_dir,
            python=ccc_py,
            column_allowed=False,
            supports_limit=False,
            supports_fresh=False,
            supports_resume=True,
            headed_flag="--headed",
            supports_description=True,
            description_default="A/M: CAPA",
            sites=(SiteVariant(key="cccone", label="CCC One (cccone.com)", script="crawler.py"),),
            notes="CCC credentials come from its .env. Choose By VIN & OEM or By VIN & PARTSLINK (Scenario).",
            input_spec=InputSpec(
                required_headers=("VIN", "OEM"),
                template_headers=("VIN", "OEM"),
                hint="Use one vehicle per row. Separate multiple OEM numbers in a cell with commas.",
            ),
            output_columns=(
                "Year", "Make", "Model", "VIN", "Partslink", "OEM", "Part Description", "Ipart listed on CCC",
                "Ipart List Price CCC", "Lowest CCC Price", "Lowest CCC Supplier",
                "Next Lowest CCC Price", "Next Lowest CCC Supplier",
                "Lowest CCC Price Supplier", "Status", "date_time", "market_data",
            ),
            output_notes="Vehicle details, input Partslink when using scenario mode, estimate Part Number in OEM and estimate Description in Part Description, iPart price, lowest and next-lowest CCC prices and suppliers, plus status and market data.",
        ),
        CrawlerSpec(
            id="keystone",
            name="Keystone",
            group="Keystone",
            script=settings.keystone_dir / "keystone_crawler.py",
            cwd=settings.keystone_dir,
            python=keystone_py,
            supports_show=True,
            supports_live_visibility=True,
            supports_manual_login=True,
            supports_resume=True,
            resume_requires_output=False,
            sites=(SiteVariant(key="orderkeystone", label="Keystone (preview.orderkeystone.com)", script="keystone_crawler.py"),),
            notes="Headless by default; login via .env. Use --show / manual login if blocked.",
            input_spec=InputSpec(
                header_alternatives=(("PARTSLINK", "Partslink Number", "Part Number"),),
                template_headers=("PARTSLINK",),
                hint="Put one Partslink number per row. Select a different column if your header uses another name.",
            ),
            output_columns=(
                "Search {search_column}", "Partslink Number (when different from search column)",
                "Oldest Year", "Newest Year", "Brand", "Model", "Type",
                "Interchange Number", "OEM Number",
                *(f"Interchange {number}" for number in range(1, 6)),
                *(f"OEM {number}" for number in range(1, 6)),
                "Number Values", "Multiple Number", "Status",
            ),
            output_notes="The search-result heading uses the selected input column. Interchange and OEM values are also expanded into numbered columns.",
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
            supports_resume=True,
            supports_show=True,
            supports_live_visibility=True,
            live_visibility_flag="--live-visibility",
            supports_manual_login=True,
            sites=(SiteVariant(key="pacificbest", label="Pacific Best (portal.pacificbestinc.com)", script="pacificbest_crawler.py"),),
            notes="Pacific Best Parts catalog. Manual login requires a visible browser; credentials are read from the project .env.",
            input_spec=InputSpec(
                header_alternatives=(("PARTSLINK", "OEM"),),
                template_headers=("PARTSLINK", "OEM"),
                hint="Include PARTSLINK and/or OEM values. Choose which column to search.",
                allow_custom_column=False,
            ),
            output_columns=(
                "PARTSLINK", "OEM", "YEAR1", "YEAR2", "MAKE", "MODEL", "DEPI",
                "CERT", "CA", "TX", "VA", "Your Price", "List Price", "Description",
            ),
        ),
        CrawlerSpec(
            id="keystone-model",
            name="Keystone by Brand",
            group="Keystone",
            script=settings.keystone_dir / "keystone_model_crawler.py",
            cwd=settings.keystone_dir,
            python=keystone_py,
            column_allowed=False,
            supports_resume=True,
            supports_show=True,
            supports_live_visibility=True,
            supports_manual_login=True,
            sites=(SiteVariant(key="orderkeystone", label="Keystone (preview.orderkeystone.com)", script="keystone_model_crawler.py"),),
            input_spec=InputSpec(
                required_headers=("Year", "Brand", "Model", "Parts", "Category"),
                template_headers=("Year", "Brand", "Model", "Parts", "Category"),
                hint="Each row describes a vehicle and the part/category to search.",
            ),
            output_columns=(
                "Partslink Number", "Oldest Year", "Newest Year", "Brand", "Model",
                "Interchange Number", "Part Type", "OEM Number",
                *(f"Interchange Number {number}" for number in range(1, 6)),
                *(f"OEM Number {number}" for number in range(1, 6)),
                "Number Values", "Description", "Search Key", "Search Status",
            ),
            output_notes="Matched part identifiers and fitment, plus part description and search status for each requested vehicle/part/category.",
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
            supports_resume=True,
            supports_live_visibility=True,
            fresh_flag="--no-resume",
            sites=(SiteVariant(key="carid", label="CARiD (www.carid.com)", script="carid_scraper.py"),),
            notes="Visible Chrome; solve Cloudflare manually when asked.",
            input_mode_scripts={
                "partslink": "carid_scraper.py",
                "interchange": "carid_interchange_scraper.py",
            },
            input_spec=InputSpec(
                header_alternatives=((
                    "PARTSLINK", "Partslink Number", "Part Number",
                    "Interchange", "Interchange Number", "Cross Reference",
                ),),
                template_headers=("PARTSLINK",),
                hint="Put one Partslink or interchange number per row. Choose the column when your workbook has both; Interchange/Cross Reference headers select interchange search.",
            ),
            output_columns=(
                "Partslink Number", "Oldest Year", "Newest Year", "Brand", "Model", "Type",
                "Interchange Number",
                *(f"Interchange {number}" for number in range(1, 6)),
                "OEM Number",
                *(f"OEM {number}" for number in range(1, 6)),
                "Number Values", "Multiple values", "Part Brand", "Product URL", "Status",
            ),
            output_notes="Partslink and Interchange searches use the same result layout, with fitment, related numbers, product link and status.",
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
            supports_resume=True,
            supports_show=False,
            supports_live_visibility=True,
            resume_requires_output=False,
            sites=(
                SiteVariant(
                    key="vininspect",
                    label="VinInspect (vininspect.com)",
                    script="scrapper_vin.py",
                    supports_fresh=True,
                    fresh_flag="--start-over",
                    input_spec=InputSpec(
                        required_headers=("Year", "Make", "Model"),
                        template_headers=("Year", "Make", "Model"),
                        hint="Each row needs a vehicle Year, Make, and Model.",
                    ),
                    output_columns=("Year", "Make", "Model", "VIN", "Status"),
                    output_notes="Vehicle year, make and model with the matched VIN and lookup status.",
                ),
                SiteVariant(
                    key="google",
                    label="Google Search (google.com)",
                    script="vin_crawler.py",
                    input_flag=None,
                    output_flag="-o",
                    supports_fresh=False,
                    input_spec=InputSpec(
                        required_headers=("Year", "Make", "Model"),
                        template_headers=("Year", "Make", "Model"),
                        hint="Each row needs a vehicle Year, Make, and Model.",
                    ),
                    output_columns=("VIN", "VIN_Source", "VIN_Candidates", "VIN_Status"),
                    output_notes="The original input columns are preserved; VIN, source, candidate matches and lookup status are added.",
                ),
                SiteVariant(
                    key="vpic",
                    label="VIN Decoder (vpic.nhtsa.dot.gov)",
                    script="vpic_decoder.py",
                    supports_fresh=True,
                    fresh_flag="--fresh",
                    input_spec=InputSpec(
                        required_headers=("VIN",),
                        template_headers=("VIN",),
                        hint="Include one VIN per row. The decoder returns Model Year, Make, and Model.",
                    ),
                    output_columns=("Year", "Make", "Model", "VIN", "Status"),
                    output_notes="Decodes each VIN with NHTSA vPIC and returns model year, make, and model.",
                ),
            ),
            notes="VinInspect and Google Search find a VIN matching Year/Make/Model. VIN Decoder looks up vehicle details from a supplied VIN.",
            output_columns=("Year", "Make", "Model", "VIN", "Status"),
        ),
        *_brand_crawlers(),
    ]
    return {s.id: s for s in specs}


CRAWLERS: dict[str, CrawlerSpec] = _registry()


def get_crawler(crawler_id: str) -> CrawlerSpec | None:
    return CRAWLERS.get(crawler_id)
