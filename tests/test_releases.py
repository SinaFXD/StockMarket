from datetime import date

import pytest

from pipeline.manual import releases as r


@pytest.mark.parametrize(
    "rule, month, due",
    [
        (r.ISM_MANUFACTURING, "2026-09", date(2026, 10, 1)),  # Thursday
        (r.ISM_MANUFACTURING, "2026-12", date(2027, 1, 4)),  # Jan 1 is a holiday, then a weekend
        (r.ISM_MANUFACTURING, "2026-08", date(2026, 9, 1)),  # Tuesday; Labor Day 2026 is Sept 7
        (r.ISM_SERVICES, "2026-09", date(2026, 10, 5)),  # Thu, Fri, Mon
        (r.NFIB, "2026-09", date(2026, 10, 13)),  # 2nd Tuesday
        (r.NFIB, "2026-12", date(2027, 1, 12)),
        (r.NBS, "2026-09", date(2026, 9, 30)),
        (r.NBS, "2028-02", date(2028, 2, 29)),  # leap year
        (r.RATINGDOG_SERVICES, "2026-12", date(2027, 1, 5)),  # Chinese calendar: only weekends skipped
    ],
)
def test_due_dates(rule, month, due):
    assert rule.due_date(month) == due


@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 9, 30), "2026-08"),
        (date(2026, 10, 1), "2026-09"),
        (date(2026, 10, 20), "2026-09"),
    ],
)
def test_latest_released_month(today, expected):
    assert r.ISM_MANUFACTURING.latest_released_month(today) == expected


def test_nbs_month_is_out_on_its_last_day():
    assert r.NBS.latest_released_month(date(2026, 10, 31)) == "2026-10"
    assert r.NBS.latest_released_month(date(2026, 10, 30)) == "2026-09"


def test_month_arithmetic_and_descriptions():
    assert r.add_months("2026-12", 1) == "2027-01"
    assert r.add_months("2027-01", -1) == "2026-12"
    assert r.add_months("2026-05", -17) == "2024-12"
    assert r.ISM_SERVICES.describe() == "3rd business day of the following month"
    assert r.NFIB.describe() == "2nd Tuesday of the following month"
    assert r.NBS.describe() == "last day of the month"
