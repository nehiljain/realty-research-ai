import os
import re
from typing import List, Tuple

import pandas as pd
from dotenv import find_dotenv, load_dotenv
from googleapiclient.discovery import build
from playwright.sync_api import sync_playwright
from thefuzz import fuzz

load_dotenv(find_dotenv())
LOCATION = "Time square New York CITY, NY"


def get_guest_room_info_cvent(url) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)

        guest_room_info = page.get_by_text("Guest RoomsTotal guest").all_inner_texts()
        # ---------------------
        context.close()
        browser.close()
        return guest_room_info


def parse_total_guest_rooms(text):
    if not text:  # Checks if the text is None or an empty string
        return None
    # Regular expression to find "Total guest rooms" followed by a number
    match = re.search(r"Total guest rooms\s+(\d+)", text)
    if match:
        return int(match.group(1))
    else:
        return None


def get_cvent_link(hotel_name, api_key, cse_id):
    # google search for cvent links
    search_term = f"cvent {hotel_name}"
    service = build("customsearch", "v1", developerKey=api_key)
    results = service.cse().list(q=search_term, cx=cse_id).execute()

    for item in results["items"]:
        if (
            fuzz.partial_ratio(hotel_name.lower(), item["title"].lower()) > 70
            and "cvent" in item["link"]
        ):
            return item["link"]
    return None


def get_room_info_for_hotel(hotel_name) -> Tuple[List[str], int]:
    hotel_name = f"{hotel_name} {LOCATION}"
    cvent_link = get_cvent_link(
        hotel_name, os.getenv("GOOGLE_CSE_API_KEY"), os.getenv("GOOGLE_CSE_ID")
    )
    if not cvent_link:
        return None
    print(f"Found cvent link: {cvent_link}")
    room_info = get_guest_room_info_cvent(url=cvent_link)
    room_info_str = "\n".join(room_info)
    total_room_info = parse_total_guest_rooms(room_info_str)
    print(f"Total guest rooms: {total_room_info}")
    return (room_info, total_room_info)


def main():
    hotel_df = pd.read_parquet("data/legit_time_square_nyc_hotel_names.parquet")
    hotel_list = hotel_df["name"].to_list()
    room_info = []
    error_list = []
    for hotel in hotel_list:
        print(hotel)
        try:
            result = get_room_info_for_hotel(hotel)
            if not result:
                continue
        except Exception as e:
            print(f"Error: {e}")
            error_list.append(hotel)
            continue
        all_info, total_num_rooms = result
        room_info.append((hotel, all_info, total_num_rooms))
        print(f"Updated room_info list with {hotel}")
        print("\n\n")
        print("---------------------------------------------------")
        print("\n\n")
    # convert the room_info list to a pandas DataFrame
    room_info_df = pd.DataFrame(
        room_info, columns=["hotel", "all_info", "total_num_rooms"]
    )
    # save the DataFrame to a parquet file
    room_info_df.to_parquet("data/cvent_room_info.parquet")
    # save the error list to a text file
    with open("data/error_list_cvent_room_info_hotels.txt", "w") as f:
        for item in error_list:
            f.write(f"{item}\n")


if __name__ == "__main__":
    main()