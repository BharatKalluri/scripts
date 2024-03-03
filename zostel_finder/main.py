import dataclasses
from http.client import HTTPException

import requests
import typer
from rich import print
from typing_extensions import Annotated


@dataclasses.dataclass
class ZostelClient:
    token: str
    client_app_id: str
    client_user_id: str

    @staticmethod
    def get_zostel_properties_list() -> list[dict]:
        response_json = requests.get(
            "https://api.zostel.com/api/v1/stay/operators/?fields=name,type_code,operating_model,latitude,longitude,code,slug,destination"
        ).json()
        return response_json["operators"]

    @staticmethod
    def get_operator_room_details(operator_id: str) -> list[dict]:
        response_json = requests.get(
            f"https://api.zostel.com/api/v1/stay/operators/{operator_id}/",
        ).json()
        rooms: list[dict] = response_json.get("operator", {}).get("rooms")
        return rooms

    def get_availability(
        self,
        check_in: str,
        check_out: str,
        property_code: str,
        room_codes_interested_in: list[int],
    ):
        response = requests.get(
            f"https://api.zostel.com/api/v1/stay/availability/?checkin={check_in}&checkout={check_out}&property_code={property_code}",
            headers={
                "authorization": self.token,
                "client-app-id": self.client_app_id,
                "client-user-id": self.client_user_id,
            },
        )
        if not response.ok:
            raise HTTPException(
                f"status code {response.status_code}. content: {response.text}"
            )
        response_json = response.json()
        availability_data = response_json.get("availability")
        filtered = list(
            filter(
                lambda x: x.get("room_id") in room_codes_interested_in,
                availability_data,
            )
        )
        return filtered


def is_units_available(
    zostel_client: ZostelClient,
    selected_slug: str,
    check_in: str,
    check_out: str,
):
    property_code = selected_slug.split("-")[-1].upper()
    accommodation_types_data = zostel_client.get_operator_room_details(selected_slug)
    room_ids_interested_in = [
        el.get("id")
        for el in accommodation_types_data
        if "dorm" in el.get("sub_category") and "female" not in el.get("name").lower()
    ]
    availability_data = zostel_client.get_availability(
        check_in=check_in,
        check_out=check_out,
        property_code=property_code,
        room_codes_interested_in=room_ids_interested_in,
    )
    units_to_book_arr = [el.get("units") for el in availability_data]
    available_everyday = len(units_to_book_arr) > 0 and all(
        [el > 0 for el in units_to_book_arr]
    )
    return available_everyday


def cli(
    check_in_date_str: Annotated[str, typer.Option()],
    check_out_date_str: Annotated[str, typer.Option()],
    token: Annotated[str, typer.Option()],
    client_app_id: Annotated[str, typer.Option()],
    client_user_id: Annotated[str, typer.Option()],
):
    zostel_client = ZostelClient(
        token=token, client_app_id=client_app_id, client_user_id=client_user_id
    )
    zostel_list_raw = zostel_client.get_zostel_properties_list()
    zostel_list_slugs = [el.get("slug") for el in zostel_list_raw]
    available_slugs = [
        selected_slug
        for selected_slug in zostel_list_slugs
        if is_units_available(
            zostel_client=zostel_client,
            selected_slug=selected_slug,
            check_in=check_in_date_str,
            check_out=check_out_date_str,
        )
    ]
    print(
        dict(
            check_in_date_str=check_in_date_str,
            check_out_date_str=check_out_date_str,
            available_slugs=available_slugs,
        )
    )


if __name__ == "__main__":
    typer.run(cli)
