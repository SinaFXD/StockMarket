from datetime import date

import pytest
from conftest import write_csv

from pipeline.manual import freshness, load
from pipeline.manual.loader import parse_month
from pipeline.manual.schemas import CHINA_PMI, ISM_INDUSTRIES, ISM_MANUFACTURING, NFIB_SBET

TODAY = date(2026, 10, 20)
ISM_HEADER = (
    "month,pmi,new_orders,production,employment,supplier_deliveries,inventories,customers_inventories,"
    "prices,backlog,new_export_orders,imports\n"
)
ISM_REST = ",47.1,49.0,45.0,51.0,47.5,44.0,64.8,44.7,46.1,48.0"
NFIB_HEADER = (
    "month,optimism_index,plans_employment,plans_capex,plans_inventories,expect_economy_improve,"
    "expect_real_sales_higher,current_inventory,current_job_openings,expected_credit_conditions,"
    "good_time_to_expand,earnings_trends\n"
)


def ism(tmp_path, body, today=TODAY):
    return load(ISM_MANUFACTURING, write_csv(tmp_path / "ism_manufacturing.csv", ISM_HEADER + body), today)


def messages(issues):
    return [i.text() for i in issues]


def test_valid_rows_are_parsed_and_sorted(tmp_path):
    ds = ism(tmp_path, f"2026-09,49.1{ISM_REST}\n2026-08,48.7{ISM_REST}\n")
    assert ds.errors == [] and ds.warnings == []
    assert [r["month"] for r in ds.rows] == ["2026-08", "2026-09"]
    assert ds.rows[1]["pmi"] == 49.1 and ds.rows[1]["imports"] == 48.0


def test_header_only_file_is_awaiting_data(tmp_path):
    ds = ism(tmp_path, "")
    assert ds.rows == [] and ds.errors == []
    fresh = freshness(ds, TODAY)
    assert fresh["status"] == "awaiting"
    assert fresh["tracked"][0]["reason"] == "no data entered yet"


@pytest.mark.parametrize(
    "typed, suggestion",
    [
        ("2026-9", "2026-09"),
        ("2026/09", "2026-09"),
        ("2026-09-01", "2026-09"),
        ("09/2026", "2026-09"),
        ("9/1/2026", "2026-09"),
        ("Sep 2026", "2026-09"),
        ("Sep-26", "2026-09"),
        ("September 2026", "2026-09"),
        ("202609", "2026-09"),
    ],
)
def test_wrong_month_formats_get_a_suggestion(typed, suggestion):
    value, error = parse_month(typed)
    assert value is None
    assert f"did you mean {suggestion}?" in error


def test_impossible_month_gets_the_format_explained():
    value, error = parse_month("2026-13")
    assert value is None and "2026-09" in error and "YYYY-MM" in error


def test_bad_rows_are_reported_with_line_numbers_and_skipped(tmp_path):
    body = (
        f"2026-01,49.1{ISM_REST}\n"  # line 2: fine
        f"2026-2,49.1{ISM_REST}\n"  # line 3: month format
        f"2026-03,148.7{ISM_REST}\n"  # line 4: out of range
        f"2026-04,48.5%{ISM_REST}\n"  # line 5: percent sign
        f"2026-05,48,7{ISM_REST}\n"  # line 6: decimal comma -> extra column
        f"2027-01,48.5{ISM_REST}\n"  # line 7: future
    )
    ds = ism(tmp_path, body)
    assert [r["month"] for r in ds.rows] == ["2026-01"]
    text = messages(ds.errors)
    assert any(t.startswith("Line 3, column 'month'") and "2026-02" in t for t in text)
    assert any(
        t.startswith("Line 4, column 'pmi'") and "outside the allowed range 0 to 100" in t for t in text
    )
    assert any(t.startswith("Line 5, column 'pmi'") and "remove the % sign" in t for t in text)
    assert any(t.startswith("Line 6:") and "13 values" in t and "dot" in t for t in text)
    assert any(t.startswith("Line 7, column 'month'") and "future" in t for t in text)


def test_quoted_decimal_comma_is_explained(tmp_path):
    ds = ism(tmp_path, f'2026-09,"48,7"{ISM_REST}\n')
    assert "Use a dot for decimals" in ds.errors[0].message


def test_duplicate_months_are_errors_and_neither_row_is_used(tmp_path):
    ds = ism(tmp_path, f"2026-08,48.7{ISM_REST}\n2026-09,49.1{ISM_REST}\n2026-09,49.2{ISM_REST}\n")
    assert [r["month"] for r in ds.rows] == ["2026-08"]
    assert "2026-09 appears 2 times (lines 3, 4)" in ds.errors[0].message


def test_header_typos_are_caught_with_a_suggestion(tmp_path):
    header = NFIB_HEADER.replace("plans_inventories", "plans_inventory")
    ds = load(
        NFIB_SBET, write_csv(tmp_path / "nfib_sbet.csv", header + "2026-09,98.8" + ",1" * 10 + "\n"), TODAY
    )
    assert ds.rows == []
    text = " ".join(messages(ds.errors))
    assert "Did you mean 'plans_inventories'?" in text and "missing column(s): plans_inventories" in text


def test_columns_may_be_in_any_order(tmp_path):
    path = write_csv(
        tmp_path / "china_pmi.csv",
        "month,ratingdog_manufacturing,ratingdog_services,"
        "nbs_manufacturing,nbs_non_manufacturing\n2026-09,51.2,52.0,49.8,50.0\n",
    )
    ds = load(CHINA_PMI, path, TODAY)
    assert ds.errors == [] and ds.rows[0]["nbs_manufacturing"] == 49.8


def test_nfib_components_can_be_negative_but_the_index_has_limits(tmp_path):
    body = "2026-08,98.8,15,20,-3,-10,2,-5,33,-6,12,-24\n2026-09,9.88,15,20,-3,-10,2,-5,33,-6,12,-24\n"
    ds = load(NFIB_SBET, write_csv(tmp_path / "nfib_sbet.csv", NFIB_HEADER + body), TODAY)
    assert [r["month"] for r in ds.rows] == ["2026-08"]
    assert ds.rows[0]["earnings_trends"] == -24
    assert "outside the allowed range 60 to 140" in ds.errors[0].message


def test_na_markers_become_empty_cells_with_a_warning(tmp_path):
    ds = ism(tmp_path, "2026-09,49.1,N/A,49.0,45.0,51.0,47.5,44.0,64.8,44.7,46.1,\n")
    assert ds.errors == [] and ds.rows[0]["new_orders"] is None and ds.rows[0]["imports"] is None
    assert "read as an empty cell" in ds.warnings[0].message


def test_excel_bom_crlf_and_blank_lines_are_handled(tmp_path):
    path = tmp_path / "ism_manufacturing.csv"
    content = "﻿" + ISM_HEADER.replace("\n", "\r\n") + "\r\n" + f"2026-9,49.1{ISM_REST}\r\n"
    path.write_bytes(content.encode("utf-8"))
    ds = load(ISM_MANUFACTURING, path, TODAY)
    assert ds.errors[0].line == 3  # the blank line still counts


def test_gaps_and_empty_rows_are_warnings(tmp_path):
    ds = ism(tmp_path, f"2026-05,49.1{ISM_REST}\n2026-09,49.1{ISM_REST}\n2026-08,,,,,,,,,,,\n")
    text = " ".join(messages(ds.warnings))
    assert "2026-08 has no values" in text
    assert "no valid row for 2026-06 to 2026-08" in text


def test_industries_choices_ranks_and_quoted_comments(tmp_path):
    body = (
        "month,report,industry,status,rank,comment\n"
        '2026-09,Manufacturing,"Food, Beverage & Tobacco Products",Growth,1,"Demand steady, prices up"\n'
        "2026-09,manufacturing,Chemical Products,growth,two,\n"
        "2026-09,mfg,Paper Products,contraction,1,\n"
        '2026-09,manufacturing,"Food, Beverage & Tobacco Products",growth,3,\n'
    )
    ds = load(ISM_INDUSTRIES, write_csv(tmp_path / "ism_industries.csv", body), TODAY)
    text = " ".join(messages(ds.errors))
    assert "'two' must be a whole number" in text
    assert "'mfg' is not allowed; use one of: manufacturing, services" in text
    assert "Food, Beverage & Tobacco Products appears 2 times" in text
    assert ds.rows == []


def test_industry_comment_with_commas_is_kept(tmp_path):
    body = (
        "month,report,industry,status,rank,comment\n"
        '2026-09,services,Retail Trade,growth,1,"Busy, but costs up"\n'
    )
    ds = load(ISM_INDUSTRIES, write_csv(tmp_path / "ism_industries.csv", body), TODAY)
    assert ds.errors == [] and ds.rows[0]["comment"] == "Busy, but costs up" and ds.rows[0]["rank"] == 1


def test_missing_file_is_an_error(tmp_path):
    ds = load(ISM_MANUFACTURING, tmp_path / "nope.csv", TODAY)
    assert "missing" in ds.errors[0].message


# --- freshness: ok -> due (grace period) -> awaiting data -------------------------------------------


@pytest.mark.parametrize(
    "today, status",
    [
        (date(2026, 9, 30), "ok"),  # the September report is not out yet
        (date(2026, 10, 1), "due"),  # released today (1st business day of October)
        (date(2026, 10, 6), "due"),  # within the 5-day grace period
        (date(2026, 10, 7), "awaiting"),  # grace period over: shown as awaiting data, excluded from scores
    ],
)
def test_freshness_follows_the_release_calendar(tmp_path, today, status):
    ds = ism(tmp_path, f"2026-08,48.7{ISM_REST}\n", today=today)
    fresh = freshness(ds, today)
    assert fresh["status"] == status
    assert fresh["tracked"][0]["last_month"] == "2026-08"


def test_china_file_tracks_each_pmi_separately(tmp_path):
    path = write_csv(
        tmp_path / "china_pmi.csv",
        "month,nbs_manufacturing,nbs_non_manufacturing,"
        "ratingdog_manufacturing,ratingdog_services\n2026-09,49.8,50.0,,\n",
    )
    fresh = freshness(load(CHINA_PMI, path, TODAY), TODAY)
    by_column = {t["column"]: t["status"] for t in fresh["tracked"]}
    assert by_column == {
        "nbs_manufacturing": "ok",
        "nbs_non_manufacturing": "ok",
        "ratingdog_manufacturing": "awaiting",
        "ratingdog_services": "awaiting",
    }
    assert fresh["status"] == "awaiting"


def test_optional_industries_file_is_never_awaiting(tmp_path):
    path = write_csv(tmp_path / "ism_industries.csv", "month,report,industry,status,rank,comment\n")
    assert freshness(load(ISM_INDUSTRIES, path, TODAY), TODAY)["status"] == "empty"
