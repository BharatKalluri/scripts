import dataclasses
from http.client import HTTPException

import requests
import streamlit as st


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


def app():
    st.set_page_config(
        page_title="Zostel Availability Finder",
        page_icon="🏢",
        layout="wide"
    )
    st.title("Zostel Availability Finder")
    
    with st.form("zostel_search_form"):
        check_in_date = st.date_input("Check-in Date")
        check_out_date = st.date_input("Check-out Date")
        token = st.text_input("Token", type="password")
        client_app_id = st.text_input("Client App ID")
        client_user_id = st.text_input("Client User ID")
        
        submitted = st.form_submit_button("Find Available Zostels")
        
        if submitted and token and client_app_id and client_user_id:
            zostel_client = ZostelClient(
                token=token,
                client_app_id=client_app_id,
                client_user_id=client_user_id
            )
            
            with st.spinner("Fetching Zostel properties..."):
                zostel_list_raw = zostel_client.get_zostel_properties_list()
                zostel_list_slugs = [el.get("slug") for el in zostel_list_raw]
                
                available_slugs = [
                    selected_slug
                    for selected_slug in zostel_list_slugs
                    if is_units_available(
                        zostel_client=zostel_client,
                        selected_slug=selected_slug,
                        check_in=check_in_date.strftime("%Y-%m-%d"),
                        check_out=check_out_date.strftime("%Y-%m-%d"),
                    )
                ]
                
                if available_slugs:
                    st.success(f"Found {len(available_slugs)} available Zostels!")
                    st.write("**Available Zostels:**")
                    for slug in available_slugs:
                        st.markdown(f"- {slug}")
                else:
                    st.warning("No available Zostels found for the selected dates.")


if __name__ == "__main__":
    app()
