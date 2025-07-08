import os
import numpy as np
import xarray as xr
from datetime import datetime, timedelta
import copernicusmarine
import climetlab as cml
import tempfile
import pandas as pd


# Login if credentials don't already exist
if not os.path.exists(os.path.expanduser("/Users/james/.copernicusmarine/.copernicusmarine-credentials")):
    copernicusmarine.login()

dataset_id = "cmems_mod_nws_phy_anfc_0.027deg-2D_PT15M-i"

# Parameters
variables = ["uo", "vo"]

# Generate the date range
now = datetime.now()
dates = [(now + timedelta(days=i)).strftime("%Y%m%d") for i in range(1)]

# Create regex pattern
date_range = "*" + "|".join(dates) + "*FC05.nc"
print(f"Regex pattern: {date_range}")

copernicusmarine.get(
    dataset_id=dataset_id,
    skip_existing=True,
    filter=date_range,
    # file_list="files_to_download.txt"
)

output_file = "/Users/james/Documents/Git/tide-current-converter/NWSHELF_ANALYSISFORECAST_PHY_004_013/cmems_mod_nws_phy_anfc_0.027deg-2D_PT15M-i_202411/2025/07/CMEMS_v7r1_NWS_PHY_NRT_NL_01qhi_20250711_20250711_R20250707_FC05.nc"


# # Download subset
# output_nc = "tidal_currents.nc"
# subset(
#     dataset_id=dataset_id,
#     variables=variables,
#     minimum_longitude=area[1],
#     maximum_longitude=area[3],
#     minimum_latitude=area[2],
#     maximum_latitude=area[0],
#     start_datetime=start_time,
#     end_datetime=end_time,
#     output_filename=output_nc
# )
nc = output_file

# Load dataset
ds = xr.open_dataset(output_file)

ds = ds.fillna(0)

if ds.latitude[0] < ds.latitude[-1]:
    ds = ds.sortby("latitude", ascending=False)

# Calculate speed in knots and direction (bearing from north)
uo = ds["uo"]  # eastward current [m/s]
vo = ds["vo"]  # northward current [m/s]

speed = np.sqrt(uo**2 + vo**2) * 1.94384  # convert to knots
bearing = (np.arctan2(uo, vo) * 180 / np.pi) % 360  # direction from north

coords = ds.coords
speed_arr = speed.values
bearing_arr = bearing.values

current_u_arr = uo.values
current_v_arr = vo.values

north_lat, south_lat, west_long, east_long = ds.latitude[0], ds.latitude[-1], ds.longitude[0], ds.longitude[-1]
print(f"Area: {north_lat}, {west_long}, {south_lat}, {east_long}")

# Step 4: Use existing field as template for GRIB structure
# e.g., load one field for template metadata
template = cml.load_source("file", "/Users/james/Downloads/CMEMS-NW.20250707.00.grb2")
# template = cml.load_source(
#     "cds",
#     "reanalysis-era5-single-levels",
#     variable=["10m_v_component_of_wind"],
#     product_type="reanalysis",
#     area=[north_lat, west_long, south_lat, east_long],
#     date="2012-12-12",
#     data_format= "grib",
#     download_format= "unarchived",
# )



# Step 5: Write GRIB with CliMetLab
# , template = template[0]
with cml.new_grib_output("tidal_currents.grib2", template = template[0]) as out:
    # Writes each time slice as separate field, adding time metadata
    for idx, t in enumerate(ds.time.values):
        print(idx, t)
        field_time = pd.Timestamp(t)
        meta = {
            "Ni": len(ds.longitude),
            "Nj": len(ds.latitude),
            # # "latitudeOfFirstGridPointInDegrees": 40.0,
            # # "longitudeOfFirstGridPointInDegrees": 5.0,
            # # "latitudeOfLastGridPointInDegrees": 60.0,
            # # "longitudeOfLastGridPointInDegrees": 355.0,
            # # "iDirectionIncrementInDegrees": 0.25,
            # # "jDirectionIncrementInDegrees": 0.25,
            "latitudeOfFirstGridPointInDegrees": float(ds.latitude[-1]),
            "longitudeOfFirstGridPointInDegrees": float((ds.longitude[0] + 360) % 360),
            "latitudeOfLastGridPointInDegrees": float(ds.latitude[0]),
            "longitudeOfLastGridPointInDegrees": float((ds.longitude[-1] + 360) % 360),
            "iDirectionIncrementInDegrees": float(ds.longitude[1] - ds.longitude[0]),
            "jDirectionIncrementInDegrees": abs(float(ds.latitude[1] - ds.latitude[0])),
            # # "typeOfLevel": "surface",
            # # "level": 0,
            "gridType": "regular_ll",
            "date": field_time,
            # "dataDate": 20250707,
            # "type": "10,1,1"
        }

        # print(meta)
        # out.write(speed_arr[idx, :, :], metadata={**meta, "shortName": "spc"})
        # out.write(bearing_arr[idx, :, :], metadata={**meta, "shortName": "dirc"})
        out.write(speed_arr[idx, :, :], metadata={**meta})
        # out.write(bearing_arr[idx, :, :], metadata={**meta})

print("✅ GRIB2 file written: tidal_currents.grib2")

