import itertools
from http.client import HTTPException
from typing import Any, Optional, List

import pandas as pd
import requests
import typer
from diskcache import Cache
from pydantic import BaseModel
from typing_extensions import Annotated

cache = Cache("cache_dir")


class ReportEntry(BaseModel):
    user_id: str
    patient_id: str
    booking_id: str
    order_group_id: str
    source: str
    standard_lab_parameter_id: str
    standard_lab_parameter_name: str
    value: str
    unit: str
    low_value: str
    high_value: str
    page_number: Any
    line_number: Any
    validated: Any
    created_at: str
    report_parameter_id: str
    report_parameter_name: str
    report_package_name: str
    inference: Optional[str]
    reference_range: Optional[str]
    display_text: Optional[str]
    observation: str
    category: str


class Report(BaseModel):
    entries: list[ReportEntry]


@cache.memoize()
def get_report(report_id: str, cookie: str, member_id: str):
    response = requests.get(
        url=f"https://www.1mg.com/pwa-api/api/v5/user/health-record/diagnostics/{report_id}/{member_id}",
        headers={"cookie": cookie},
    )
    if not response.ok:
        raise HTTPException(
            f"failed to retrieve report {report_id}. status code {response.status_code}, content {response.text}"
        )
    return response.json()


def parse_json_report(report_contents: dict) -> Report:
    parameters = report_contents.get("data", {}).get("parameters", [])
    report_values: list[dict] = list(
        itertools.chain(*[p.get("values", {}) for p in parameters])
    )
    return Report(entries=report_values)


def build_biomarker_db(
    report_ids: list[str], cookie: str, member_id: str
) -> list[ReportEntry]:
    reports: list[Report] = [
        parse_json_report(
            get_report(
                report_id=report_id,
                cookie=cookie,
                member_id=member_id,
            )
        )
        for report_id in report_ids
    ]
    report_entries: list[ReportEntry] = list(
        itertools.chain(*[r.entries for r in reports])
    )
    return report_entries


app = typer.Typer(rich_markup_mode="markdown")


@app.command(rich_help_panel="help")
def cli(
    cookie: Annotated[
        str, typer.Option(help="cookie from any authenticated tata 1mg request")
    ],
    member_id: Annotated[
        str, typer.Option(help="member ID from the /health-record url")
    ],
    report_id: Annotated[
        List[str],
        typer.Option(help="report ID from /health-record/<member-id> report urls"),
    ],
):
    """
        **context**:

        unfortunately, tata 1mg does not make it easy to get data out of their systems. this exporter expects you

        - to change the user agent to ios / chrome using a user agent switcher, retrieve cookie from an authenticated request

        - get the member ID from the /health-record page

        - get report IDs from /health-record/<member-id> page and supply them as args so that we can scrape and build the csv.

    ---

        the csv will be piped out which can later be used to create file
    """
    if None in [report_id, cookie, member_id]:
        print("invalid arguments")
        return
    biomarker_db: list[ReportEntry] = build_biomarker_db(
        report_id, cookie=cookie, member_id=member_id
    )
    df = pd.DataFrame.from_records([el.dict() for el in biomarker_db])
    print(df.to_csv())


if __name__ == "__main__":
    app()
