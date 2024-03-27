import folium
from branca.element import Element

colors = {
    "Marriott International": "#B71234",
    "InterContinental Hotels Group (IHG)": "#5E2750",
    "Baccarat": "#D4AF37",
    "OYO Rooms": "#E52929",
    "Choice Hotels International": "#3D9AD1",
    "Hilton Worldwide": "#004B87",
    "RIU": "#F5821F",
    "Accor": "#4A4A4A",  # Adjusted description to dark grey for clarity
    "StarHotels": "#0072B1",
    "Wyndham Hotels & Resorts": "#8CC63F",
    "Hyatt Hotels Corporation": "#58707E",
    "Hard Rock Hotels": "#1C1C1B",
    "Millenium Hotels": "#A7A9AC",
    "Triumph Hotels": "#CBA258",
    "Royalton Hotels": "#4169E1",
    "Citizen M": "#FF00FF",
    "Dream Hotels": "#6A0DAD",
    "Warwick Hotels": "#720E0E",
    "Independent": "#30BFBF",
}


def get_brand_colors_mapping(hotel_df):
    return hotel_df["brand"].apply(lambda x: colors[x])


# Function to add a legend to the map
def add_legend(map_obj, title, colors, labels):
    legend_html = (
        """
     <div style="position: fixed; 
                 bottom: 50px; left: 50px; width: 250px; height: 580px; 
                 border:0.1px solid grey; z-index:9999; font-size:14px;
                 background-color:white;
                 ">&nbsp; <b>"""
        + title
        + """</b> <br>
                 &nbsp; Legend <br>
                 {}
                  </div>
     """
    )
    legend_entries = ""
    for label, color in colors.items():
        legend_entry = f'<p><i style="background:{color};width:12px;height:12px;float:left;margin-right:5px;"></i>{label}</p>'
        legend_entries += legend_entry

    legend_html = legend_html.format(legend_entries)

    legend_element = Element(legend_html)
    map_obj.get_root().html.add_child(legend_element)


def get_map(hotel_df):
    # Prepare the legend labels (brands) and colors
    legend_labels = hotel_df["brand"].unique().tolist()
    legend_colors = colors  # The custom color palette

    hotels_df = hotel_df.copy()
    # filter out hotels with total_num_of_rooms less than 0
    hotels_df = hotels_df[hotels_df["total_num_of_rooms"] > 0]

    # normalize the number of rooms in a new col from 0-10
    hotels_df["total_num_of_rooms_normalized"] = (
        hotels_df["total_num_of_rooms"] - hotels_df["total_num_of_rooms"].min()
    ) / (
        hotels_df["total_num_of_rooms"].max() - hotels_df["total_num_of_rooms"].min()
    ) * 9 + 1

    # Times Square coordinates
    times_square_lat, times_square_lon = 40.7580, -73.9855
    # Create a map centered at Times Square
    map_ts_hotels = folium.Map(
        location=[times_square_lat, times_square_lon],
        zoom_start=15,
        tiles="CartoDB positron",
    )

    # Define a color scale for the number of rooms. More rooms => darker color
    color_scale = folium.LinearColormap(
        ["green", "yellow", "red"],
        vmin=hotels_df["total_num_of_rooms_normalized"].min(),
        vmax=hotels_df["total_num_of_rooms_normalized"].max(),
    )

    # Add hotel markers to the map
    for idx, row in hotels_df.iterrows():
        # Marker size based on the number of rooms
        marker_size = row[
            "total_num_of_rooms_normalized"
        ]  # Scale factor to adjust sizes visually

        # Create a circle marker for each hotel
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=marker_size,
            popup=f"{row['name']}<br>Rooms: {row['total_num_of_rooms']}",
            color=row["color"],
            fill=True,
        ).add_to(map_ts_hotels)

    # Adding the color scale to the map
    color_scale.add_to(map_ts_hotels)
    add_legend(map_ts_hotels, "Hotel Brands", legend_colors, legend_labels)
    # Display the map
    return map_ts_hotels