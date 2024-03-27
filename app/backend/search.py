import logging
import os
import re
from enum import Enum
from pathlib import Path

import instructor
import pandas as pd
import streamlit as st
from dotenv import find_dotenv, load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from serpapi import GoogleSearch
from tqdm import tqdm

load_dotenv(find_dotenv())
logger = logging.getLogger(__name__)


def get_output_path(filename):
    # write a function to get path from .env or create a data folder to store the output
    # add the filename to the path
    output_path = Path(os.getenv("OUTPUT_PATH", "data"))
    output_path.mkdir(exist_ok=True)
    return output_path / filename


def slugify(text):
    # write a function to slugify the text for filename
    pattern = r"[^\w+]"
    return re.sub(pattern, "-", text.lower().strip())


@st.cache_data
def fetch_all_hotels(query, api_key):
    all_hotels = []
    params = {
        "api_key": api_key,
        "engine": "google_hotels",
        "q": query,
        "hl": "en",
        "gl": "us",
        "check_in_date": "2024-05-21",
        "check_out_date": "2024-05-22",
        "currency": "USD",
        "num": "20",
    }

    while True:
        search = GoogleSearch(params)
        results = search.get_dict()
        all_hotels += results.get("properties", [])

        # Check if there are more pages
        if "serpapi_pagination" in results and "next" in results["serpapi_pagination"]:
            params["next_page_token"] = results["serpapi_pagination"]["next_page_token"]
        else:
            break
    # return a new list of hotels with only the name, description, gps_coordinates, link, hotel_class

    result_df = pd.DataFrame(
        [
            {
                "name": hotel.get("name"),
                "description": hotel.get("description"),
                "latitude": hotel.get("gps_coordinates", {}).get("latitude"),
                "longitude": hotel.get("gps_coordinates", {}).get("longitude"),
                "link": hotel.get("link"),
                "hotel_class": hotel.get("hotel_class"),
            }
            for hotel in all_hotels
        ]
    )
    return result_df


class LegitHotel(BaseModel):
    name: str
    is_legit_name: bool = Field("True if the name of the hotel is legit.")


def get_hotel_name_legitimacy(hotel_name):
    client = instructor.patch(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "user",
                "content": f"Is the <name> {hotel_name} </name> a real hotel name. Examples of real hotel names: New York Hilton Midtown, Hotel Edison New York City, ROW NYC. Example of fake hotel name: Located In Midtown! Trendy Bars, Pet-friendly, Close To Broadway!,A Trip To The Most Vibrant City! Onsite Dining, Pet-friendly, Near Central Park!, Spacious Room in The Heart of Manhattan",
            }
        ],
        response_model=LegitHotel,
    )
    # parse the content to get the number of room
    return resp


@st.cache_data
def filter_legit_hotels(hotel_df):
    legitamacy_results = []

    all_pages_results = hotel_df.to_dict(orient="records")
    for hotel in tqdm(all_pages_results):
        try:
            legit_hotel = get_hotel_name_legitimacy(hotel["name"])
        except Exception as e:
            print(f"Error processing {hotel['name']}: {e}")
            continue
        legitamacy_results.append(legit_hotel)

    # filter hotel_df based on the legitamacy_results
    legitamacy_results_df = pd.DataFrame(
        [result.dict() for result in legitamacy_results]
    )
    print(legitamacy_results_df)
    filtered_hotel_df = hotel_df.merge(legitamacy_results_df, on="name")
    filtered_hotel_df = filtered_hotel_df[filtered_hotel_df["is_legit_name"] == True]
    return filtered_hotel_df


class HotelSubbrandLevel(Enum):
    Luxury = "Luxury"
    Premium = "Premium"
    Midscale = "Midscale"
    Resort = "Resort"
    Economy = "Economy"
    BedAndBreakfast = "Bed and Breakfast"
    Hostel = "Hostel"
    Apartment = "Apartment"


class HotelBrand(Enum):
    Hilton = "Hilton Worldwide"
    Marriott = "Marriott International"
    IHG = "InterContinental Hotels Group (IHG)"
    Wyndham = "Wyndham Hotels & Resorts"
    Hyatt = "Hyatt Hotels Corporation"
    Accor = "Accor"
    Choice = "Choice Hotels International"
    BestWestern = "Best Western Hotels & Resorts"
    Radisson = "Radisson Hotel Group"
    OYO = "OYO Rooms"
    Airbnb = "Airbnb"
    Independent = "Independent"


class Hotel(BaseModel):
    name: str
    brand: HotelBrand = Field(
        None,
        description="Brand of the hotel based on the name. If the name is not a hotel, return None. If not a recognized brand, return Independent.",
    )
    subbrand: HotelSubbrandLevel = Field(
        None,
        description="Subbrand of the hotel based on the name. If the name is not a hotel, return None.",
    )
    total_num_of_rooms: int = Field(
        ..., description="Total Number of rooms in the hotel"
    )


gpt4_prompt = """
How many rooms are there in hotel <hotel_name>{hotel_name} </hotel_name>. Give answer with citations.

For brands and subbrand levels, use the following:
1. Marriott International
Luxury: The Ritz-Carlton, St. Regis, JW Marriott, The Luxury Collection, W Hotels, Edition, Bulgari Hotels & Resorts, Ritz-Carlton Reserve
Premium: Marriott Hotels, Sheraton, Marriott Vacation Club, Delta Hotels, Le Méridien, Westin, Renaissance Hotels, Gaylord Hotels, Autograph Collection Hotels
Midscale: , SpringHill Suites, Protea Hotels, Fairfield by Marriott, AC Hotels, Aloft Hotels, Moxy Hotels, Element by Westin
Courtyard by Marriott, Four Points
2. Hilton Worldwide
Luxury: Waldorf Astoria Hotels & Resorts, Conrad Hotels & Resorts, LXR Hotels & Resorts
Premium: Hilton Hotels & Resorts, Canopy by Hilton, Signia Hilton, Curio Collection by Hilton, DoubleTree by Hilton, Tapestry Collection by Hilton, Embassy Suites by Hilton
Midscale: Hilton Garden Inn, Hampton by Hilton, Tru by Hilton, Homewood Suites by Hilton, Tempo by Hilton
Economy: Home2 Suites by Hilton, Motto by Hilton
3. InterContinental Hotels Group (IHG)
Luxury: Six Senses Hotels Resorts Spas, Regent Hotels & Resorts, InterContinental Hotels & Resorts, Kimpton Hotels & Restaurants
Premium: Voco, Hotel Indigo, HUALUXE Hotels and Resorts, Crowne Plaza Hotels & Resorts
Midscale: Holiday Inn, Holiday Inn Express, Holiday Inn Club Vacations, Avid Hotels
Economy: Staybridge Suites, Candlewood Suites, Atwell Suites
4. Wyndham Hotels & Resorts
Luxury: Registry Collection Hotels
Premium: Wyndham Grand, Dolce Hotels and Resorts
Midscale: Wyndham, Ramada, TRYP by Wyndham, Wingate by Wyndham, Hawthorn Suites by Wyndham, Microtel by Wyndham, Trademark Collection by Wyndham
Economy: Days Inn, Super 8, Howard Johnson, Travelodge, La Quinta, AmericInn, Baymont, Knights Inn
5. Accor
Luxury: Raffles, Fairmont, Sofitel, Orient Express, MGallery, Pullman
Premium: Swissôtel, 25hours Hotels, Mövenpick Hotels & Resorts, Grand Mercure, Peppers, Banyan Tree, Art Series, Mondrian, SLS
Midscale: Novotel, Mercure, Adagio, Mama Shelter, Tribe, Mantra
Economy: ibis, ibis Styles, ibis budget, HotelF1, Jo&Joe, Greet
6. Choice Hotels
Luxury: N/A
Premium: Cambria Hotels, The Ascend Hotel Collection
Midscale: Clarion, Quality Inn, Sleep Inn, Comfort Inn, Comfort Suites
Economy: Econo Lodge, Rodeway Inn, MainStay Suites, Suburban Extended Stay, Woodspring Suites
7. Best Western
Luxury: BW Premier Collection, WorldHotels Luxury, WorldHotels Elite
Premium: Best Western Premier, Vīb, GLō, Sadie, Aiden
Midscale: Best Western, Best Western Plus, Executive Residency by Best Western
Economy: SureStay Hotel by Best Western, SureStay Plus Hotel by Best Western, SureStay Studio by Best Western, SureStay Collection by Best Western
8. Hyatt Hotels Corporation
Luxury: Park Hyatt, Miraval, Grand Hyatt, Andaz
Premium: , Hyatt, Hyatt Place, Hyatt House, Alila, Thompson Hotels, Hyatt Centric, The Unbound Collection by Hyatt, Destination Hotels, Joie de Vivre, Caption by Hyatt
Midscale:Hyatt Regency
Economy: N/A
9.Radisson International
Luxury: N/A
Premium: Jin Jiang Hotels, Radisson Collection, Radisson Blu
Midscale: Radisson, Radisson RED, Radisson Individuals, Park Plaza, Park Inn by Radisson
Economy: 7 Days Inn, Jinjiang Inn, Metropolo, Country Inn & Suites by Radisson, Radisson Hotel Group
10. OYO Rooms
Luxury: OYO Townhouse, Collection O
Premium: Palette, SilverKey, Capital O
Midscale: OYO Rooms, OYO Home
Economy: OYO Life, OYO Flagship
"""


def get_hotel_details_from_md_gpt4(hotel_name):
    client = instructor.patch(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
    resp = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "user",
                "content": f"How many rooms are there in hotel <hotel_name>{hotel_name} </hotel_name>. Give answer with citations.",
            }
        ],
        response_model=Hotel,
    )
    # parse the content to get the number of rooms
    return resp


def parse_hotel_pydantic_object(obj):
    return {
        "name": obj.name,
        "brand": obj.brand.value if obj.brand else None,
        "subbrand": obj.subbrand.value if obj.subbrand else None,
        "total_num_of_rooms": obj.total_num_of_rooms,
    }


def get_hotel_details(hotel_df):
    results = []

    all_pages_results = hotel_df.to_dict(orient="records")
    for hotel in tqdm(all_pages_results):
        try:
            gpt_hotel = get_hotel_details_from_md_gpt4(hotel["name"])
        except Exception as e:
            print(f"Error processing {hotel['name']}: {e}")
            continue
        results.append(gpt_hotel)
    return pd.DataFrame([parse_hotel_pydantic_object(obj) for obj in results])


@st.cache_data
def combine_hotel_data(hotel_df, hotel_details_df):
    all_names = hotel_df.name.to_list()
    output = []
    for index, row in hotel_details_df.iterrows():
        hotel_name = [name for name in all_names if row["name"] == name]
        if len(hotel_name) == 0:
            continue

        # get the row with the saved_hotel_name
        matched_row = hotel_df[hotel_df["name"] == hotel_name].iloc[0]
        output.append(
            {
                "name": matched_row["name"],
                "latitude": matched_row["latitude"],
                "longitude": matched_row["longitude"],
                "link": matched_row["link"],
                "star_rating": matched_row["hotel_class"],
                "brand": row["brand"],
                "scale": row["subbrand"],
                "total_num_of_rooms": row["total_num_of_rooms"],
            }
        )
    # return a new DataFrame with the combined data and remove any duplicates on names
    # also remove any rows with missing values for latitude, longitude, name
    return (
        pd.DataFrame(output)
        .drop_duplicates(subset=["name"], keep="first")
        .dropna(subset=["latitude", "longitude", "name"])
    )
