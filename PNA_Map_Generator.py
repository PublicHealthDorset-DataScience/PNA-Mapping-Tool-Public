import streamlit as st
import pandas as pd
import geopandas as gpd
import requests
import folium
from streamlit_folium import folium_static
import credentials
import gzip
import random

access_token = credentials.access_token # Add your Mapbox access token here

color_list = ['lightgreen','purple','red', 'blue', 'green',  'orange', 
                'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 
                'cadetblue', 'darkpurple','pink', 'lightblue', 
                 'gray', 'black', 'lightgray']



def generate_color_dict(keys, colors):
    # Create an empty dictionary
    color_dict = {}    
    # Iterate over the list of keys
    for i, key in enumerate(keys):
        # Assign a random color from the colors list
        #color_dict[key] = random.choice(colors)
        # Use modulus to ensure colors wrap around if there are more keys than colors
        color_dict[key] = colors[i % len(colors)]    
    return color_dict

# Function to convert the string to title case
def title_case_converter(x, col_name):
    if col_name == "ODS_CODE":
        return x
    elif isinstance(x, str):
        return x.title()
    return x

# Define a lambda function to assign values based on the condition
assign_activity = lambda x: 'Closed' if x == 'Closed' else 'Opened'

# Function to process the pharmacy data
def process_pharmacy_df(pharmacy_data,postcode_lookup_df):
    cols = ['ORGANISATION_NAME','ADDRESS_FIELD_1','ADDRESS_FIELD_2', 'ADDRESS_FIELD_3', 'ADDRESS_FIELD_4',
            'POST_CODE']
    pharmacy_data['CONCATENATED_ADDRESS'] = pharmacy_data[cols].astype(str).apply(lambda x: ','.join(x.dropna().astype(str)), axis=1)
    merged_df = pd.merge(pharmacy_data, postcode_lookup_df, left_on = 'POST_CODE', right_on='postcode')
    merged_df = merged_df[['PHARMACY_OPENING_HOURS_SATURDAY','PHARMACY_OPENING_HOURS_THURSDAY','CONTRACT_TYPE','PHARMACY_OPENING_HOURS_TUESDAY',
                        'HEALTH_AND_WELLBEING_BOARD','PHARMACY_OPENING_HOURS_FRIDAY','WEEKLY_TOTAL','PHARMACY_OPENING_HOURS_WEDNESDAY',
                        'PHARMACY_OPENING_HOURS_MONDAY','PHARMACY_ODS_CODE__F_CODE_','PHARMACY_OPENING_HOURS_SUNDAY','CONCATENATED_ADDRESS',
                        'latitude','longitude']]
    merged_df.rename(columns = {'PHARMACY_OPENING_HOURS_SATURDAY':'Opening_Hours_Saturday',
                                'PHARMACY_OPENING_HOURS_THURSDAY':'Opening_Hours_Thursday',
                                'CONTRACT_TYPE':'Organisation_Type',
                                'PHARMACY_OPENING_HOURS_TUESDAY':'Opening_Hours_Tuesday',
                                'HEALTH_AND_WELLBEING_BOARD': 'LA',
                                'PHARMACY_OPENING_HOURS_FRIDAY':'Opening_Hours_Friday',
                                'WEEKLY_TOTAL':'Total_Opening_Hours' ,
                                'PHARMACY_OPENING_HOURS_WEDNESDAY': 'Opening_Hours_Wednesday',
                                'PHARMACY_OPENING_HOURS_MONDAY':'Opening_Hours_Monday' ,
                                'PHARMACY_ODS_CODE__F_CODE_':'ODS_CODE' ,
                                'PHARMACY_OPENING_HOURS_SUNDAY':'Opening_Hours_Sunday',
                            'longitude':'Longitude',
                            'latitude':'Latitude'}, inplace = True)

    # Apply the function to the DataFrame
    merged_df = merged_df.apply(lambda col: col.apply(lambda x: title_case_converter(x, col.name) if merged_df.columns.name != "ODS_CODE" else x))

    merged_df['Weekday'] = 'Opened'
    merged_df['Weekend_Saturday'] = merged_df['Opening_Hours_Saturday'].apply(assign_activity)
    merged_df['Weekend_Sunday'] = merged_df['Opening_Hours_Sunday'].apply(assign_activity)

    merged_df = merged_df[['ODS_CODE','CONCATENATED_ADDRESS','Organisation_Type','LA','Opening_Hours_Monday','Opening_Hours_Tuesday','Opening_Hours_Wednesday',
                            'Opening_Hours_Thursday','Opening_Hours_Friday','Opening_Hours_Saturday','Opening_Hours_Sunday','Total_Opening_Hours',
                        'Weekday','Weekend_Saturday','Weekend_Sunday','Longitude','Latitude']]

    pharmacy_data_processed = merged_df
    return pharmacy_data_processed

# Function to create a map
def create_pharmcy_map(pharmacy_data_processed, geo_data, pharmacy_colours):
    # Create a map centered at the mean latitude and longitude
    m = folium.Map(location=[pharmacy_data_processed['Latitude'].mean(), 
                            pharmacy_data_processed['Longitude'].mean()],
                             tiles= 'cartodbpositron', zoom_start=9)

        
    # Iterate over DataFrame rows and add markers to the map
    for index, pharmacy in pharmacy_data_processed.iterrows():
        # Determine marker color based on zone
        color = pharmacy_colours.get(pharmacy['LA'], 'black')

        popup_html = f"""
                    <b>Code:</b> {pharmacy['ODS_CODE']}<br>
                    <b>Name:</b> {pharmacy['CONCATENATED_ADDRESS']}<br>        
                    <b>Local Authority:</b> {pharmacy['LA']}<br>
                    <b>Organisation Type:</b> {pharmacy['Organisation_Type']}<br>
                    <b>Opening Hours Monday:</b> {pharmacy['Opening_Hours_Monday']}<br>
                    <b>Opening Hours Tuesday:</b> {pharmacy['Opening_Hours_Tuesday']}<br>
                    <b>Opening Hours Wednesday:</b> {pharmacy['Opening_Hours_Wednesday']}<br>
                    <b>Opening Hours Thursday:</b> {pharmacy['Opening_Hours_Thursday']}<br>
                    <b>Opening Hours Friday:</b> {pharmacy['Opening_Hours_Friday']}<br>
                    <b>Opening Hours Saturday:</b> {pharmacy['Opening_Hours_Saturday']}<br>
                    <b>Opening Hours Sunday:</b> {pharmacy['Opening_Hours_Sunday']}<br>
                    <b>Total Opening Hours:</b> {pharmacy['Total_Opening_Hours']}<br>
                    """
        
        pharmacy_location = (pharmacy['Latitude'], pharmacy['Longitude'])
        
        folium.Marker(location=pharmacy_location,
                    popup=folium.Popup(popup_html, max_width=300),
                    icon=folium.Icon(color=color, icon_color='white', icon='hospital', prefix='fa'),
                    tooltip = 'Click for more details').add_to(m)

    # Add hover functionality.
    map_style_function = lambda x: {'fillColor': '#ffffff', 
                                'color':'#000000', 
                                'fillOpacity': 0.1, 
                                'weight': 1}
    map_highlight_function = lambda x: {'fillColor': '#000000', 
                                    'color':'#000000', 
                                    'fillOpacity': 0.50, 
                                    'weight': 0.1}
    folium.GeoJson(data = geo_data, 
                style_function=map_style_function,
                highlight_function=map_highlight_function, 
                control=False,).add_to(m)
    return m

# Function to fetch isochrone data from Mapbox Isochrone API
def get_isochrone(lon, lat, profile, minutes):
    url = f"https://api.mapbox.com/isochrone/v1/mapbox/{profile}/{lon},{lat}?contours_minutes={minutes}&polygons=true&denoise=1&access_token={access_token}" #&generalize=500
    response = requests.get(url)
    return response.json()

# Function to fetch isochrone data from Mapbox Isochrone API
def get_isochrone_data(pharmacy_df, travel_modes, travel_times, activity):
    all_isochrone_data = []

    for index, row in pharmacy_df.iterrows():
        pharmacy_isochrone_data = {}
        if row[activity] == 'Opened':  # Check if the pharmacy is opened
            for travel_mode in travel_modes:
                for minutes in travel_times:
                    # Get isochrone data for the pharmacy location, travel mode, and travel time
                    isochrone_data = get_isochrone(row['Longitude'], row['Latitude'], travel_mode, minutes)
                    key = f'{travel_mode}_{minutes}mins'
                    pharmacy_isochrone_data[key] = isochrone_data
        else:
            for travel_mode in travel_modes:
                for travel_time in travel_times:
                    pharmacy_isochrone_data[f'{travel_mode}_{travel_time}mins'] = {'features': [], 'type': 'FeatureCollection'}

        all_isochrone_data.append((row, pharmacy_isochrone_data))

    return all_isochrone_data

def create_isochrone_map(m, travel_mode, travel_time, all_isochrone_data):   
    # Define the style function for the isochrone borders
    iso_borders_styles_function = lambda x: {'color': '#009900',
                                             'weight': 1,
                                             'fillColor': '#009900',
                                             'fillOpacity': 0.3}

    
    # Create feature groups to group isochrones by travel time
    travel_time_groups = {f'{travel_time}mins': folium.FeatureGroup(name=f'{travel_time} mins by {travel_mode}')}           
    # Add markers to the map
    for pharmacy, pharmacy_isochrone_data in all_isochrone_data:
        for key, isochrone_data in pharmacy_isochrone_data.items():
            # Extract travel time from the key
            travel_time = int(key.split('_')[-1][:-4])  # Extract the minutes
            
            # Verify if isochrone data is not empty and has valid features
            if isochrone_data and 'features' in isochrone_data:
                # Create GeoJson object for the isochrone
                iso_geojson = folium.GeoJson(
                    isochrone_data,
                    name=f'{travel_time}mins',
                    style_function = iso_borders_styles_function)
                
                # Add the GeoJson to the appropriate feature group
                if f'{travel_time}mins' in travel_time_groups:
                    travel_time_groups[f'{travel_time}mins'].add_child(iso_geojson)

    # Add all feature groups to the map
    for group in travel_time_groups.values():
        group.add_to(m)

    # Add hover functionality.
    boundary_layer = folium.FeatureGroup(name='Show Boundary', show=True)
    map_style_function = lambda x: {'fillColor': '#ffffff', 
                                'color':'#000000', 
                                'fillOpacity': 0.1, 
                                'weight': 1}

    folium.GeoJson(data = geo_data, 
                style_function=map_style_function).add_to(boundary_layer)
    boundary_layer.add_to(m)
    # Add layer control to the map to switch between map tiles and isochrone layers
    folium.TileLayer('cartodbpositron').add_to(m)
    folium.LayerControl().add_to(m)
    return m

# Load the postcode lookup data
#postcode_lookup_df = pd.read_csv('data/ukpostcodes.csv')
postcode_lookup_df_path = 'data/ukpostcodes.csv.gz'
with gzip.open(postcode_lookup_df_path, 'rb') as f:
    postcode_lookup_df = pd.read_csv(f)
postcode_lookup_df = postcode_lookup_df[['postcode','latitude','longitude']]

# Initialize the session state for run_button if it does not exist
if 'pharmacy_data_upload' not in st.session_state:
    st.session_state['pharmacy_data_upload'] = False
if 'geo_file_upload' not in st.session_state:
    st.session_state['geo_file_upload'] = False
if 'create_isochrone_map_button' not in st.session_state:
    st.session_state['create_isochrone_map_button'] = False


st.title('PNA Isochrone Map Generator')
st.write('**Use the sidebar to upload your pharmacy data and boundary geojson file**')


# Add a sidebar
with st.sidebar:
    st.subheader('About the Tool')
    st.write('This tool allows you to create an isochrone map for your uploaded pharmacy data, showing the travel times to pharmacies in the area.')
    st.write('You can use the sidebar to upload your pharmacy data') 
    st.write('Select the travel mode and travel time and day type in the main window and click button to create an isochrone map.')
    st.write('The map is interactive, so you can zoom in and out, and click on the markers to see more information about each site.')

    pharmacy_data_uploaded_file = st.file_uploader("Uplaod your pharmacy csv file", type=['csv'], key='pharmacy_data_key')
    geo_file = st.file_uploader("**Upload your area's boundary geojson file**", type=['json'], key='geo_file_key')
    if pharmacy_data_uploaded_file is not None:
        pharmacy_data = pd.read_csv(pharmacy_data_uploaded_file)
        st.session_state['pharmacy_data_upload'] = True
        
    if geo_file is not None:
        geo_data = gpd.read_file(geo_file)
        st.session_state['geo_file_upload'] = True
    
    #Add reset button
    if st.button('Reset'):       
        st.session_state['pharmacy_data_upload'] = False
        st.session_state['geo_file_upload'] = False
        st.session_state['create_isochrone_map_button'] = False
        st.session_state.pop('geo_file_key')
        st.session_state.pop('pharmacy_data_key')
        st.rerun()

try:
    if st.session_state['pharmacy_data_upload'] not in [False, None] and st.session_state['geo_file_upload'] not in [False, None]:
        with st.expander('Click here to view the pharmacy data'):
            pharmacy_data_processed = process_pharmacy_df(pharmacy_data,postcode_lookup_df)
            st.dataframe(pharmacy_data_processed)  

        with st.form("run_form"):   
            col1, col2, col3 = st.columns(3)
            with col1:         
                # Add activity selectbox to the sidebar:
                activity = st.selectbox('Select Day: ',('Weekday', 'Weekend_Saturday', 'Weekend_Sunday'))
            with col3:
                #Add travel times to sidebar
                travel_time = st.selectbox('Select Travel Time (Mins): ',(5, 10, 15, 20, 25, 30), index=3)

            col4, col5, col6 = st.columns(3)
            with col4:
                # Add travel selectbox to the sidebar:
                travel_mode = st.selectbox('Select Travel Mode: ',('walking','cycling','driving', 'driving-traffic'), 
                                        index=2)
            # with col6:
            #     show_top_percentage = st.number_input('Prescribe/Dispense Pop-up table filter:', 1, 100, 5)
            
            # Add a button to create the isochrone map
            st.write("**Click the button below to create an isochrone map**")
            create_isochrone_map_button = st.form_submit_button("Create Isochrone Map")

            if create_isochrone_map_button:
                st.session_state['create_isochrone_map_button'] = True
            
            if st.session_state['create_isochrone_map_button'] == False:
                # Display the map
                with st.spinner('Creating map...'):
                    # Assign a color to each area
                    area_list = pharmacy_data_processed['LA'].unique()
                    pharmacy_colours = generate_color_dict(area_list, color_list)

                    m = create_pharmcy_map(pharmacy_data_processed, geo_data,pharmacy_colours)
                    folium_static(m,width=670, height=400)
                    st.success("Map created successfully!")
            else:     
                with st.spinner('Creating isochrone map...'):
                    all_isochrone_data = get_isochrone_data(pharmacy_data_processed, [travel_mode], [travel_time], activity)
                    # Assign a color to each area
                    area_list = pharmacy_data_processed['LA'].unique()
                    pharmacy_colours = generate_color_dict(area_list, color_list)
                    m = create_pharmcy_map(pharmacy_data_processed, geo_data,pharmacy_colours)
                    m = create_isochrone_map(m, travel_mode, travel_time, all_isochrone_data)
                    folium_static(m,width=670, height=400)
                    st.success("Isochrone map created successfully!")
except Exception as e:
    st.warning(""" Something went wrong.
                Please check the following:
                1. The uploaded pharmacy data and boundary geojson file are in correct format.
                2. The Mapbox API token is correct.
                3. Try again.""")


