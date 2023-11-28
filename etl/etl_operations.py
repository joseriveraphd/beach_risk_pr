from datetime import datetime
import pandas as pd
import datetime as dt
import geopandas as gpd
from shapely import wkt
import os

s3_directory = os.environ.get('S3_BUCKET_DIRECTORY')

###########
# Extract:
# Pull data from National Weather Prediction website
###########

def get_highres_risk_level() -> pd.DataFrame:
    """
    Get high-resolution risk level data from experimental prediction website NWPS
    """
    # Read risk level associated with rip current stations throughout island
    url = 'https://polar.ncep.noaa.gov/nwps/images/rtimages/validation/SJU1.rip'
    # file_data = requests.get(url).content

    try:
        df = pd.read_csv(url, sep="|", names=['sju_ripprob'])
        print("Data successfully extracted from NWPS website.")
    except:
        print("Failed to extract data from NWPS website.")

    # Transform risk level data into dataframe with appropriate names
    df = df['sju_ripprob'].str.split('|', expand=True)
    df.columns = ['stat_name', 'lat', 'long', 'rip_current_station', 'origin', 'color', 'risk_level']

    # Add timestamp to data
    df['date_time'] = pd.Series([dt.datetime.now()] * len(df))

    # Clean risk level column by removing comma
    df['risk_level'] = df['risk_level'].str[:-1]

    return df

###########
# Transform:
# Join National Weather Predictive Service to beach geometries on rip current station coordinates to
# the nearest beach centroid
###########


def compute_beach_centroids() -> gpd.GeoDataFrame:
    """
    Compute centroid of all beaches with polygon objects
    """

    beach_by_zone = pd.read_csv(s3_directory + '/final_beach_list_zones_geom.csv')  # contains surf zone and beach geometry
    beach_by_zone['geometry'] = beach_by_zone['geometry'].apply(
        wkt.loads)  # gpd is unable to convert geometry from csv, so need wkt conversion.

    gdf = gpd.GeoDataFrame(beach_by_zone, crs='epsg:4326')

    # Project to NAD83 projected crs
    gdf = gdf.to_crs(epsg=2263)

    # Access the centroid attribute of each polygon
    gdf["centroid"] = gdf.centroid

    # Project to WGS84 geographic crs

    # geometry (active) column
    gdf = gdf.to_crs(epsg=4326)

    # Centroid column
    gdf["centroid"] = gdf["centroid"].to_crs(epsg=4326)

    return gdf


def assign_beach_risk_level() -> gpd.GeoDataFrame:
    """
    Join beach data with risk level data downloaded from National Weather Prediction service (NWPS)
    to create a geospatial dataframe gdf. The gdf contains beaches joined to the nearest rip current station.
    Beach risk level is classified according to the nearest rip current station risk level.

    The output is a dataframe with NWPS beach data that has been joined to beaches by matching beach centroids to their
    nearest rip current station.

    A beach is assigned a risk level based on the nearest rip current station.
    """
    # Convert rip stations to geospatial dataframe
    rip_stations = get_highres_risk_level()
    rip_cs = gpd.GeoDataFrame(rip_stations, geometry=gpd.points_from_xy(rip_stations.long, rip_stations.lat))
    rip_cs.crs = "EPSG:4326"

    # The tricky join
    beach = compute_beach_centroids()

    beach.to_crs(epsg=4326)
    rip_cs.to_crs(epsg=4326)

    join_beaches = beach.sjoin_nearest(rip_cs, how="inner", max_distance=1)
    return join_beaches

###########
# Load
# ###########


def save_to_s3(clean_data: pd.DataFrame):
    """
    Save a copy of beach risk data to S3
    """
    df = clean_data

    file_date = datetime.now().strftime("%Y_%m_%d-%I_%M_%p")
    file_prefix = 'raw_rcs_'
    file_suffix = '.csv'

    s3_path = s3_directory
    s3_key = file_prefix + file_date + file_suffix
    s3_address = s3_path + s3_key

    try:
        df.to_csv(s3_address, sep='|', index=False)
        print("DataFrame uploaded to S3 successfully.")
    except:
        print("An error occurred sending to S3.")

