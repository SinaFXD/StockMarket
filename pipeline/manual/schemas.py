"""What each hand-entered CSV in ``data/manual/`` must look like.

The column lists match the header rows already in the files; ``data/manual/README.md`` explains them
to the user. Ranges are hard limits that catch typos, not opinions about the data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import releases
from .releases import ReleaseRule


@dataclass(frozen=True)
class Column:
    name: str
    kind: str  # month | diffusion | net_pct | level | choice | rank | text
    label: str = ""
    min: float | None = None
    max: float | None = None
    choices: tuple[str, ...] = ()
    required: bool = False

    @property
    def is_value(self) -> bool:
        return self.kind in {"diffusion", "net_pct", "level"}


@dataclass(frozen=True)
class Tracked:
    """A column whose freshness is monitored against the report's release calendar."""

    column: str
    label: str
    release: ReleaseRule


@dataclass(frozen=True)
class ManualFile:
    name: str
    title: str
    source: str
    columns: tuple[Column, ...]
    key: tuple[str, ...] = ("month",)
    tracked: tuple[Tracked, ...] = ()
    optional: bool = False
    sort: tuple[str, ...] = field(default=("month",))

    @property
    def filename(self) -> str:
        return f"{self.name}.csv"

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


MONTH = Column("month", "month", "Month (YYYY-MM)", required=True)


def diffusion(name: str, label: str) -> Column:
    return Column(name, "diffusion", label, 0, 100)


def net_pct(name: str, label: str) -> Column:
    return Column(name, "net_pct", label, -100, 100)


ISM_MANUFACTURING = ManualFile(
    name="ism_manufacturing",
    title="ISM Manufacturing PMI",
    source="ISM Report On Business (ismworld.org)",
    columns=(
        MONTH,
        diffusion("pmi", "PMI (headline)"),
        diffusion("new_orders", "New Orders"),
        diffusion("production", "Production"),
        diffusion("employment", "Employment"),
        diffusion("supplier_deliveries", "Supplier Deliveries"),
        diffusion("inventories", "Inventories"),
        diffusion("customers_inventories", "Customers' Inventories"),
        diffusion("prices", "Prices"),
        diffusion("backlog", "Backlog of Orders"),
        diffusion("new_export_orders", "New Export Orders"),
        diffusion("imports", "Imports"),
    ),
    tracked=(Tracked("pmi", "ISM Manufacturing PMI", releases.ISM_MANUFACTURING),),
)

ISM_SERVICES = ManualFile(
    name="ism_services",
    title="ISM Services PMI",
    source="ISM Report On Business (ismworld.org)",
    columns=(
        MONTH,
        diffusion("pmi", "Services PMI (headline)"),
        diffusion("business_activity", "Business Activity"),
        diffusion("new_orders", "New Orders"),
        diffusion("employment", "Employment"),
        diffusion("supplier_deliveries", "Supplier Deliveries"),
        diffusion("inventories", "Inventories"),
        diffusion("prices", "Prices"),
        diffusion("backlog", "Backlog of Orders"),
        diffusion("new_export_orders", "New Export Orders"),
        diffusion("imports", "Imports"),
        diffusion("inventory_sentiment", "Inventory Sentiment"),
    ),
    tracked=(Tracked("pmi", "ISM Services PMI", releases.ISM_SERVICES),),
)

ISM_INDUSTRIES = ManualFile(
    name="ism_industries",
    title="ISM industries & respondent comments",
    source="ISM Report On Business (ismworld.org)",
    columns=(
        MONTH,
        Column("report", "choice", "Report", choices=("manufacturing", "services"), required=True),
        Column("industry", "text", "Industry", required=True),
        Column("status", "choice", "Status", choices=("growth", "contraction"), required=True),
        Column("rank", "rank", "Rank in ISM's list"),
        Column("comment", "text", "Respondent comment"),
    ),
    key=("month", "report", "industry"),
    optional=True,
    sort=("month", "report", "status", "rank"),
)

NFIB_SBET = ManualFile(
    name="nfib_sbet",
    title="NFIB Small Business Optimism",
    source="NFIB Small Business Economic Trends (nfib.com)",
    columns=(
        MONTH,
        Column("optimism_index", "level", "Optimism Index (1986=100)", 60, 140),
        net_pct("plans_employment", "Plans to increase employment"),
        net_pct("plans_capex", "Plans to make capital outlays"),
        net_pct("plans_inventories", "Plans to increase inventories"),
        net_pct("expect_economy_improve", "Expect economy to improve"),
        net_pct("expect_real_sales_higher", "Expect real sales higher"),
        net_pct("current_inventory", "Current inventory"),
        net_pct("current_job_openings", "Current job openings"),
        net_pct("expected_credit_conditions", "Expected credit conditions"),
        net_pct("good_time_to_expand", "Now a good time to expand"),
        net_pct("earnings_trends", "Earnings trends"),
    ),
    tracked=(Tracked("optimism_index", "NFIB Optimism Index", releases.NFIB),),
)

CHINA_PMI = ManualFile(
    name="china_pmi",
    title="China PMIs (NBS official & RatingDog)",
    source="NBS (stats.gov.cn); RatingDog China PMI by S&P Global (formerly Caixin)",
    columns=(
        MONTH,
        diffusion("nbs_manufacturing", "NBS manufacturing PMI"),
        diffusion("nbs_non_manufacturing", "NBS non-manufacturing PMI"),
        diffusion("ratingdog_manufacturing", "RatingDog manufacturing PMI"),
        diffusion("ratingdog_services", "RatingDog services PMI"),
    ),
    tracked=(
        Tracked("ratingdog_manufacturing", "RatingDog manufacturing PMI", releases.RATINGDOG_MANUFACTURING),
        Tracked("ratingdog_services", "RatingDog services PMI", releases.RATINGDOG_SERVICES),
        Tracked("nbs_manufacturing", "NBS manufacturing PMI", releases.NBS),
        Tracked("nbs_non_manufacturing", "NBS non-manufacturing PMI", releases.NBS),
    ),
)

MANUAL_FILES: tuple[ManualFile, ...] = (ISM_MANUFACTURING, ISM_SERVICES, ISM_INDUSTRIES, NFIB_SBET, CHINA_PMI)
