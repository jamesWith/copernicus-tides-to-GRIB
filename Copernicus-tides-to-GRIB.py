import os
import xarray as xr
from datetime import datetime, timedelta
import copernicusmarine
from eccodes import *


# Login if credentials don't already exist
if not os.path.exists(os.path.expanduser("/Users/james/.copernicusmarine/.copernicusmarine-credentials")):
    copernicusmarine.login()

dataset_id = "cmems_mod_nws_phy_anfc_0.027deg-2D_PT15M-i"

# Parameters
variables = ["uo", "vo"]

# Generate the date range
now = datetime.now()
dates = [(now + timedelta(days=i)).strftime("%Y%m%d") for i in range(10)]
date_pattern = "|".join(dates)


print(f"Dates to download: {dates}")

# Create regex pattern
date_regex = rf".*_({date_pattern})_.*FC.*\.nc$"
print(f"Regex pattern: {date_regex}")

# Create a file to store the list of downloaded files
to_download_list_txt = "tide_forecasts_to_download.txt"
current_forecast_file_list_txt = "current_forecast_files.txt"

if os.path.exists(to_download_list_txt):
    os.remove(to_download_list_txt)
if os.path.exists(current_forecast_file_list_txt):
    os.remove(current_forecast_file_list_txt)

# Get the list of files to download
copernicusmarine.get(
    dataset_id=dataset_id,
    regex=date_regex,
    skip_existing=True,
    create_file_list=to_download_list_txt
)

# Get the list of files to use for current forecast
copernicusmarine.get(
    dataset_id=dataset_id,
    regex=date_regex,
    create_file_list=current_forecast_file_list_txt
)

with open(to_download_list_txt, "r") as f:
    downloads_list = f.read().splitlines()
    for index, item in enumerate(downloads_list):
        # Keep the file path after "native"
        downloads_list[index] = item.split("native/")[-1]

with open(current_forecast_file_list_txt, "r") as f:
    current_forecast_list = f.read().splitlines()
    for index, item in enumerate(current_forecast_list):
        # Keep the file path after "native"
        current_forecast_list[index] = item.split("native/")[-1]

# Check user is happy to download the files
# If the list is empty, exit
if downloads_list != []:
    print(f"Files to download:\n")
    for file in downloads_list:
        print(file)
    confirm = input("Do you want to download these files? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Download cancelled.")
        exit()

# Actually download the files 
copernicusmarine.get(
    dataset_id=dataset_id,
    skip_existing=True,
    regex=date_regex,
    file_list=current_forecast_file_list_txt
)

# Set current working directory to current directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

u_current_ds_list = []
v_current_ds_list = []

for index, forecast_file in enumerate(current_forecast_list):
    # Load dataset
    ds = xr.open_dataset(forecast_file)

    # Fill NaN values with 0
    ds = ds.fillna(0)

    # Make sure the data is in the correct order by latitude
    if ds.latitude[0] < ds.latitude[-1]:
        ds = ds.sortby("latitude", ascending=False)

    # Use the first dataset to get the area and grid information
    # Will be the same for all datasets, so only do this once
    if index == 0:

        north_lat, south_lat, west_long, east_long = float(ds.latitude[0]), float(ds.latitude[-1]), float(ds.longitude[0]), float(ds.longitude[-1])
        Ni, Nj = len(ds.longitude), len(ds.latitude)
        di, dj = float(ds.longitude[1] - ds.longitude[0]), abs(float(ds.latitude[1] - ds.latitude[0]))
        
        print(f"Area: {north_lat}, {west_long}, {south_lat}, {east_long}")

    # Calculate speed in knots and direction (bearing from north)
    uo = ds["uo"]  # eastward current [m/s]
    vo = ds["vo"]  # northward current [m/s]

    u_knots = uo * 1.94384  # convert to knots
    v_knots = vo * 1.94384  # convert to knots

    u_current_ds_list.append(u_knots)
    v_current_ds_list.append(v_knots)

u_current_array = xr.concat(u_current_ds_list, dim="time")
v_current_array = xr.concat(v_current_ds_list, dim="time")

def write_field(filename, values, short_name, step):
    gid = codes_grib_new_from_samples("regular_ll_sfc_grib2")
    codes_set(gid, "Ni", Ni)
    codes_set(gid, "Nj", Nj)
    codes_set(gid, "gridType", "regular_ll")
    codes_set(gid, "latitudeOfFirstGridPointInDegrees", north_lat)
    codes_set(gid, "longitudeOfFirstGridPointInDegrees", west_long)
    codes_set(gid, "latitudeOfLastGridPointInDegrees", south_lat)
    codes_set(gid, "longitudeOfLastGridPointInDegrees", east_long)
    codes_set(gid, "iDirectionIncrementInDegrees", di)
    codes_set(gid, "jDirectionIncrementInDegrees", dj)
    codes_set(gid, "discipline", 10)  # Oceanographic products
    codes_set(gid, "parameterCategory", 1)  # Currents
    codes_set(gid, "parameterNumber", 2 if short_name == "ocu" else 3)  # Speed or direction
    # codes_set(gid, "parameterNumber", 1 if short_name == "spc" else 2)  # Speed or direction
    
    # Leaving in this here as a reminder programs and packages are conflicted on some current "shortName" values
    # qtVlm couldnt read "spc" or "dirc", but xyGrib could. Eccodes doesnt recognise "ocu", "ocv" or "uogrd", "vogrd".
    # Ignoring the "shortName", and just using the parameterNumber that refers U-current and V-current.
    # See these links for a combination of what might work with different programs:
    # https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-2-10-1.shtml
    # https://codes.ecmwf.int/grib/param-db/?discipline=10&category=1
    # codes_set(gid, "shortName", short_name) 

    # codes_set(gid, "dataDate", 20250709)  # Example date, replace with actual date
    codes_set(gid, "dataDate", int(now.strftime("%Y%m%d")))
    codes_set(gid, "dataTime", 0)
    codes_set(gid, "stepUnits", "m") 
    codes_set(gid, "step", step * 15)  # Convert step to minutes
    codes_set(gid, "stepType", "instant")
    codes_set(gid, "typeOfLevel", "surface")
    codes_set(gid, "level", 0)
    codes_set_values(gid, values.flatten(order="C"))

    with open(filename, "ab") as f:
        codes_write(gid, f)
    codes_release(gid)

# Something to delete the file if it exists
if os.path.exists("tidal_currents.grib2"):
    os.remove("tidal_currents.grib2")

for idx, t in enumerate(u_current_array.time.values):
    write_field("tidal_currents.grib2", u_current_array.values[idx, :, :], "ocu", idx)
    write_field("tidal_currents.grib2", v_current_array.values[idx, :, :], "ocv", idx)
