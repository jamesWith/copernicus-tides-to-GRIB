# copernicus_tides_to_grib.py
# Copyright (C) 2025 James Withers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.


import os
import argparse
import xarray as xr
from datetime import datetime, timedelta
import copernicusmarine
from eccodes import *

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download Copernicus Marine tidal forecast data and convert to GRIB2"
    )
    parser.add_argument("-t", "--temporal-resolution", type=str,
                        default="15m",
                        help="Time between data points (multiple of 15 mins) e.g.'15m' or '6h'")
    parser.add_argument("-s", "--spatial-resolution-factor", type=int,
                        default=1,
                        help="Factor to adjust spatial resolution. Default is 1 (no change). Use 2 for half resolution.")
    parser.add_argument("-d", "--days", type=int, default=5,
                        help="Number of forecast days. Default is 5 days. Must be between 1 and 10.")
    parser.add_argument("-i", "--dataset-id", type=str,
                        default="cmems_mod_nws_phy_anfc_0.027deg-2D_PT15M-i",
                        help="Dataset ID to download from Copernicus Marine. Default is 'cmems_mod_nws_phy_anfc_0.027deg-2D_PT15M-i'.")
    parser.add_argument("-l", "--low-data", action="store_true",
                        help="Enable low-data mode. NOT YET IMPLEMENTED")
    parser.add_argument("-o", "--output-dir", type=str, default=os.path.dirname(os.path.abspath(__file__)),
                        help="Directory for forecast files and grib output")
    parser.add_argument("-g", "--grib-filename", type=str, default="tidal_currents.grib2",
                        help="Filename for the output GRIB file. Default is 'tidal_currents.grib2'.")
    parser.add_argument("-c", "--credentials-dir", type=str, default="~",
                        help="Directory for Copernicus Marine credentials. Will look for '/.copernicusmarine/' folder in this directory, which should contain '.copernicusmarine-credentials.'")
    parser.add_argument("-k", "--keep-forecasts", action="store_true",
                        help="Don't delete forecast NetCDFs files after GRIB export")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output. NOT YET IMPLEMENTED")
    return parser.parse_args()


def check_credentials(credentials_dir):
    """
    Check if the Copernicus Marine credentials file exists.
    If not, prompt the user to log in.
    """
    credentials_path = os.path.expanduser(os.path.join(credentials_dir, ".copernicusmarine", ".copernicusmarine-credentials"))
    if not os.path.exists(credentials_path):
        print("Credentials file not found. Please log in to Copernicus Marine.")
        copernicusmarine.login()
    else:
        print("Credentials file found. Proceeding with download.")

def download_files(args, to_download_list_path, current_forecast_file_list_path):
    """
    Get the list of files to download and the current forecast files, 
    And then download them.
    """
    # Generate the date range
    dates = [(datetime.now() + timedelta(days=i)).strftime("%Y%m%d") for i in range(args.days)]

    print(f"Dates to download: {dates}")

    # Create regex pattern
    date_pattern = "|".join(dates)
    date_regex = rf".*_({date_pattern})_.*FC.*\.nc$"

    if os.path.exists(to_download_list_path):
        os.remove(to_download_list_path)
    if os.path.exists(current_forecast_file_list_path):
        os.remove(current_forecast_file_list_path)

    # change file name to path name and just get file name for get request

    # Get the list of files to download
    # Documentation: https://toolbox-docs.marine.copernicus.eu/en/stable/python-interface.html
    copernicusmarine.get(
        dataset_id=args.dataset_id,
        regex=date_regex,
        output_directory=args.output_dir,
        skip_existing=True,
        create_file_list=os.path.basename(to_download_list_path)
    )

    # Get the list of files to use for current forecast
    copernicusmarine.get(
        dataset_id=args.dataset_id,
        regex=date_regex,
        output_directory=args.output_dir,
        create_file_list=os.path.basename(current_forecast_file_list_path)
    )

    with open(to_download_list_path, "r") as f:
        downloads_list = f.read().splitlines()
        for index, item in enumerate(downloads_list):
            # Keep the file path after "native"
            downloads_list[index] = item.split("native/")[-1]

    with open(current_forecast_file_list_path, "r") as f:
        current_forecast_list = f.read().splitlines()
        for index, item in enumerate(current_forecast_list):
            # Keep the file path after "native"
            current_forecast_list[index] = os.path.expanduser(os.path.join(args.output_dir, item.split("native/")[-1]))
    
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
        dataset_id=args.dataset_id,
        skip_existing=True,
        regex=date_regex,
        output_directory=args.output_dir,
        file_list=current_forecast_file_list_path
    )
    return current_forecast_list

def collate_files(current_forecast_list):
    u_current_ds_list = []
    v_current_ds_list = []

    for forecast_file in current_forecast_list:
        # Load dataset
        ds = xr.open_dataset(forecast_file)

        # Fill NaN values with 0
        ds = ds.fillna(0)

        # Make sure the data is in the correct order by latitude
        if ds.latitude[0] < ds.latitude[-1]:
            ds = ds.sortby("latitude", ascending=False)

        # Calculate speed in knots and direction (bearing from north)
        uo = ds["uo"]  # eastward current [m/s]
        vo = ds["vo"]  # northward current [m/s]

        u_knots = uo / 1.94384  # convert to knots
        v_knots = vo / 1.94384  # convert to knots

        u_current_ds_list.append(u_knots)
        v_current_ds_list.append(v_knots)

    u_current_array = xr.concat(u_current_ds_list, dim="time")
    v_current_array = xr.concat(v_current_ds_list, dim="time")

    return u_current_array, v_current_array

def reduce_resolution(args, u_current_array, v_current_array):

    if args.temporal_resolution.endswith("m"):
        # Convert minutes to seconds for temporal resolution
        time_reduction_factor = int(int(args.temporal_resolution[:-1]) / 15)
    elif args.temporal_resolution.endswith("h"):
        time_reduction_factor = int(int(args.temporal_resolution[:-1]) * 4)
    elif args.temporal_resolution.endswith("d"):
        time_reduction_factor = int(int(args.temporal_resolution[:-1]) * 96)
    else:
        raise ValueError("Invalid temporal resolution format. Valid format e.g. '15m', '6h', or '1d'.")

    u_current_array = u_current_array.isel(time=slice(0, None, time_reduction_factor))
    v_current_array = v_current_array.isel(time=slice(0, None, time_reduction_factor))

    u_current_array = u_current_array.isel(latitude=slice(0, None, args.spatial_resolution_factor))
    v_current_array = v_current_array.isel(latitude=slice(0, None, args.spatial_resolution_factor))

    u_current_array = u_current_array.isel(longitude=slice(0, None, args.spatial_resolution_factor))
    v_current_array = v_current_array.isel(longitude=slice(0, None, args.spatial_resolution_factor))

    return u_current_array, v_current_array


def main():
    args = parse_args()
    args.output_dir = os.path.expanduser(args.output_dir).replace(".", os.path.dirname(os.path.abspath(__file__)))
    
    # Check output directory exists, if not create it
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        print(f"Created output directory: {args.output_dir}")

    # Set current working directory to current directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    check_credentials(args.credentials_dir)

    current_forecast_file_list_path = os.path.expanduser(os.path.join(args.output_dir, "current_forecast_files.txt"))
    to_download_list_path = os.path.expanduser(os.path.join(args.output_dir, "tide_forecasts_to_download.txt"))

    current_forecast_list = download_files(args, to_download_list_path, current_forecast_file_list_path)

    u_current_array, v_current_array = collate_files(current_forecast_list)

    u_current_array, v_current_array = reduce_resolution(args, u_current_array, v_current_array)

    north_lat, south_lat, west_long, east_long = float(u_current_array.latitude[0]), float(u_current_array.latitude[-1]), float(u_current_array.longitude[0]), float(u_current_array.longitude[-1])
    Ni, Nj = len(u_current_array.longitude), len(u_current_array.latitude)
    di, dj = float(u_current_array.longitude[1] - u_current_array.longitude[0]), abs(float(u_current_array.latitude[1] - u_current_array.latitude[0]))
    
    print(f"Area: {north_lat}, {west_long}, {south_lat}, {east_long}")

    grib_path = os.path.expanduser(os.path.join(args.output_dir, args.grib_filename))

    # Something to delete the file if it exists
    if os.path.exists(grib_path):
        os.remove(grib_path)

    def write_field(values, short_name, step):
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
        # Documentation for codes: https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-2-10-1.shtml


        # Leaving in this here as a reminder programs and packages are conflicted on some current "shortName" values
        # qtVlm couldnt read "spc" or "dirc", but xyGrib could. Eccodes doesnt recognise "ocu", "ocv" or "uogrd", "vogrd".
        # Ignoring the "shortName", and just using the parameterNumber that refers U-current and V-current.
        # See these links for a combination of what might work with different programs:
        # https://www.nco.ncep.noaa.gov/pmb/docs/grib2/grib2_doc/grib2_table4-2-10-1.shtml
        # https://codes.ecmwf.int/grib/param-db/?discipline=10&category=1
        # codes_set(gid, "shortName", short_name) 

        # codes_set(gid, "dataDate", 20250709)  # Example date, replace with actual date
        codes_set(gid, "dataDate", int(datetime.now().strftime("%Y%m%d")))
        codes_set(gid, "dataTime", 0)
        codes_set(gid, "stepUnits", args.temporal_resolution[-1])  # 'm' for minutes, 'h' for hours
        codes_set(gid, "step", step * int(args.temporal_resolution[:-1]))
        codes_set(gid, "stepType", "instant")
        codes_set(gid, "typeOfLevel", "surface")
        codes_set(gid, "level", 0)
        codes_set_values(gid, values.flatten(order="C"))

        with open(grib_path, "ab") as f:
            codes_write(gid, f)
        codes_release(gid)

    for idx, t in enumerate(u_current_array.time.values):
        write_field(u_current_array.values[idx, :, :], "ocu", idx)
        write_field(v_current_array.values[idx, :, :], "ocv", idx)

    if not args.keep_forecasts:
        # Delete the forecast NetCDF files
        for file in current_forecast_list:
            if os.path.exists(file):
                os.remove(file)
                print(f"Deleted file: {file}")
            else:
                print(f"File not found: {file}")

if __name__ == "__main__":
    main()
