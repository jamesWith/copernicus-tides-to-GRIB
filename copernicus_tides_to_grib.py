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
from eccodes import codes_grib_new_from_samples, codes_set, codes_set_values, codes_write, codes_release
import re
import logging
import sys

# Area bounds: {area_code: (min_lat, max_lat, min_lon, max_lon)}
AREA_BOUNDS = {
    "chnl": (48, 52, -7, 0),       # English Channel / Celtic Sea
    "irish": (50, 56, -12, -4),    # Irish Sea / Celtic Sea
    "north": (51, 62, -5, 10),     # North Sea
    "biscay": (43, 48, -10, 0),    # Bay of Biscay
    "salcombe-lizard": (49.887557, 50.412018, -5.339355, -3.460693),  # Salcombe to Lizard coordinates
}

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
    parser.add_argument("-d", "--days", type=int, default=4,
                        help="Number of forecast days. Default is 4 days. Must be between 1 and 10.")
    parser.add_argument("-i", "--dataset-id", type=str,
                        default="cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i",
                        help="Dataset ID to download from Copernicus Marine. Default is 'cmems_mod_nws_phy-cur_anfc_1.5km-2D_PT15M-i'.")
    parser.add_argument("-l", "--low-data", action="store_true",
                        help="Enable low-data mode. NOT YET IMPLEMENTED")
    parser.add_argument("-o", "--output-dir", type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_folder"),
                        help="Directory for forecast files and grib output")
    parser.add_argument("-g", "--grib-filename", type=str, default="tidal_currents.grib2",
                        help="Filename for the output GRIB file. Default is 'tidal_currents.grib2'.")
    parser.add_argument("-c", "--credentials-dir", type=str, default="~",
                        help="Directory for Copernicus Marine credentials. Will look for '/.copernicusmarine/' folder in this directory, which should contain '.copernicusmarine-credentials.'")
    parser.add_argument("-r", "--delete-forecasts", action="store_true",
                        help="Delete forecast NetCDFs files after GRIB export")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output. NOT YET IMPLEMENTED")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Assume yes for prompts (non-interactive)")
    parser.add_argument("-a", "--area", type=str, default="chnl",
                        choices=list(AREA_BOUNDS.keys()),
                        help=f"Area to download data for. Available: {', '.join(AREA_BOUNDS.keys())}")
    return parser.parse_args()



def check_credentials(credentials_dir):
    """
    Check if the Copernicus Marine credentials file exists.
    If not, prompt the user to log in.
    """
    credentials_path = os.path.expanduser(os.path.join(credentials_dir, ".copernicusmarine", ".copernicusmarine-credentials"))
    if not os.path.exists(credentials_path):
        logging.info("Credentials file not found. Attempting interactive login.")
        try:
            copernicusmarine.login()
            logging.info("Login succeeded; credentials stored.")
        except Exception as e:
            logging.error("Login failed: %s", e)
            raise
    else:
        logging.debug("Credentials file found at %s", credentials_path)

def download_files_using_subset(args):
    # Look up area bounds
    if args.area not in AREA_BOUNDS:
        raise ValueError(f"Unknown area '{args.area}'. Available areas: {', '.join(AREA_BOUNDS.keys())}")
    min_lat, max_lat, min_lon, max_lon = AREA_BOUNDS[args.area]

    # Get current time in ISO format for dateutil parsing
    request_start_date = datetime.now().date()
    logging.info("Start time: %s", request_start_date)
    request_end_date = (datetime.now().date() + timedelta(days=args.days))
    logging.info("End time: %s", request_end_date)

    dash_range_re = re.compile(r"(\d{4}-\d{2}-\d{2})-(\d{4}-\d{2}-\d{2})")
    ymd_re = re.compile(r"(\d{8})")

    forecast_start_end_dates = []

    existing_files = [f for f in os.listdir(args.output_dir) if f.endswith(".nc")]
    for file in existing_files:
        # Prefer dash-separated start-end pattern if present (e.g. 2026-04-09-2026-04-15)
        m = dash_range_re.search(file)
        if m:
            file_start_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            file_end_date = datetime.strptime(m.group(2), "%Y-%m-%d").date()
        else:
            # Fallback: look for any 8-digit YYYYMMDD tokens in the filename
            matches = ymd_re.findall(file)
            if len(matches) >= 2:
                dts = [datetime.strptime(x, "%Y%m%d").date() for x in matches]
                file_start_date = min(dts)
                file_end_date = max(dts)
            elif len(matches) == 1:
                file_start_date = datetime.strptime(matches[0], "%Y%m%d").date()
                file_end_date = file_start_date
            else:
                # no date information found -> skip
                continue

        # Delete file if it is in the past
        if file_end_date < datetime.now().date():
            os.remove(os.path.join(args.output_dir, file))
            print(f"Deleted file: {file}")
            continue

        # Add the start and end date to the list
        forecast_start_end_dates.append((file_start_date, file_end_date, file))

    # Sort the forecast by start date
    forecast_start_end_dates = sorted(forecast_start_end_dates, key=lambda x: x[0])
    logging.info("Found %d existing forecast files.", len(forecast_start_end_dates))
    logging.debug("Forecast start and end dates:")
    for start_date, end_date, file in forecast_start_end_dates:
        logging.debug("File: %s Start: %s End: %s", file, start_date, end_date)

    # Create array to hold dates and file names for useful forecasts
    useful_forecasts_files = []

    # Find which forecasts are useful (consecutive forecasts)
    previous_end_date = None
    for forecast_start_date, forecast_end_date, file in forecast_start_end_dates:
        if previous_end_date is None:
            # if it is the earliest forecast
            if forecast_start_date <= request_start_date:
                # If it starts before today, add it to the useful forecasts and change the previous end date
                useful_forecasts_files.append(os.path.join(args.output_dir, file))
                previous_end_date = forecast_end_date
            else:
                # If the first forecast starts after today, break and get all new forecasts
                break
        else:
            # If this is is not the first forecast, check if it is consecutive with the previous useful forecast
            if forecast_start_date == previous_end_date:
                # If it is consecutive, add it to the useful forecasts
                useful_forecasts_files.append(os.path.join(args.output_dir, file))
                previous_end_date = forecast_end_date
    
    # Set end of current forecasts to last useful forecast end date
    # If there are no useful forecasts, set it to the start date of the request
    current_forecasts_end_date = previous_end_date if previous_end_date is not None else request_start_date

    if current_forecasts_end_date < request_end_date:
        # If the current forecasts end date is before the requested end date, we need to download more forecasts
        download_info = copernicusmarine.subset(
            dataset_id=args.dataset_id,
            skip_existing=True,
            start_datetime=current_forecasts_end_date.isoformat(),
            end_datetime=request_end_date.isoformat(),
            minimum_latitude=min_lat,
            maximum_latitude=max_lat,
            minimum_longitude=min_lon,
            maximum_longitude=max_lon,
            output_directory=args.output_dir,
            netcdf_compression_level=9,
            dry_run=True
        )
        logging.info("Download info: filename=%s output_dir=%s size_mb=%s transfer_mb=%s", download_info.filename, download_info.output_directory, download_info.file_size, download_info.data_transfer_size)
        logging.info("Start time: %s End time: %s", download_info.coordinates_extent[2].minimum, download_info.coordinates_extent[2].maximum)

        if not getattr(args, "yes", False):
            confirm = input("Do you want to download this data? (yes/no): ").strip().lower()
            if confirm not in ["yes", "y", "YES", "Y"]:
                logging.info("Download cancelled.")
                sys.exit(0)
        else:
            logging.info("Auto-confirmed download via --yes flag.")
        
        download_info = copernicusmarine.subset(
            dataset_id=args.dataset_id,
            skip_existing=True,
            start_datetime=current_forecasts_end_date.isoformat(),
            end_datetime=request_end_date.isoformat(),
            minimum_latitude=min_lat,
            maximum_latitude=max_lat,
            minimum_longitude=min_lon,
            maximum_longitude=max_lon,
            output_directory=args.output_dir,
            netcdf_compression_level=9,
            dry_run=False
        )
        useful_forecasts_files.append(os.path.join(args.output_dir, download_info.filename))
    return useful_forecasts_files


def download_files(args):
    """
    Get the list of files to download and the current forecast files, 
    And then download them.
    """

    current_forecast_file_list_path = os.path.expanduser(os.path.join(args.output_dir, "current_forecast_files.txt"))
    to_download_list_path = os.path.expanduser(os.path.join(args.output_dir, "tide_forecasts_to_download.txt"))

    # Generate the date range
    dates = [(datetime.now() + timedelta(days=i)).strftime("%Y%m%d") for i in range(args.days)]


    # Get current time in ISO format for dateutil parsing
    start_time = datetime.now().isoformat()
    end_time = (datetime.now() + timedelta(days=args.days)).isoformat()
    logging.info("Start time: %s", start_time)
    logging.info("End time: %s", end_time)
    logging.info("Dates to download: %s", dates)

    # Create regex pattern: accept both YYYYMMDD and YYYY-MM-DD variants so
    # files with dashed dates are matched (e.g. 2026-04-09)
    date_alts = []
    for d in dates:
        date_alts.append(d)
        date_alts.append(f"{d[0:4]}-{d[4:6]}-{d[6:8]}")
    date_pattern = "|".join(date_alts)
    date_regex = rf".*({date_pattern}).*\.nc$"

    if os.path.exists(to_download_list_path):
        os.remove(to_download_list_path)
    if os.path.exists(current_forecast_file_list_path):
        os.remove(current_forecast_file_list_path)

    # change file name to path name and just get file name for get request

    """
    Get dates/times that user wants to download.
    Look at downloaded files to see what is already there.
    Adjust times to the gap between requested dates and existing files.
    Get files using subset.

    """

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
        logging.info("Files to download:\n")
        for file in downloads_list:
            logging.info(file)
        if not getattr(args, "yes", False):
            confirm = input("Do you want to download these files? (yes/no): ").strip().lower()
            if confirm not in ["yes", "y", "YES", "Y"]:
                logging.info("Download cancelled.")
                sys.exit(0)
        else:
            logging.info("Auto-confirmed download via --yes flag.")


    # Actually download the files 
    copernicusmarine.get(
        dataset_id=args.dataset_id,
        skip_existing=True,
        regex=date_regex,
        output_directory=args.output_dir,
        file_list=current_forecast_file_list_path
    )
    return current_forecast_list

def collate_files(current_forecast_list, args):
    u_current_ds_list = []
    v_current_ds_list = []

    for forecast_file in current_forecast_list:
        # Load dataset and ensure resources are released promptly
        with xr.open_dataset(forecast_file) as ds:
            # Fill NaN values with 0 (consider masking in future)
            ds = ds.fillna(0)

            # Make sure the data is in the correct order by latitude
            if ds.latitude[0] < ds.latitude[-1]:
                ds = ds.sortby("latitude", ascending=False)

            # Calculate speed in knots and direction (bearing from north)
            uo = ds["uo"].load()  # eastward current [m/s]
            vo = ds["vo"].load()  # northward current [m/s]

            u_knots = uo / 1.94384  # convert to knots
            v_knots = vo / 1.94384  # convert to knots

            # Append DataArrays with loaded data so dataset can be closed
            u_current_ds_list.append(u_knots)
            v_current_ds_list.append(v_knots)

    u_current_array = xr.concat(u_current_ds_list, dim="time")
    v_current_array = xr.concat(v_current_ds_list, dim="time")

    # Crop to requested area bounds
    min_lat, max_lat, min_lon, max_lon = AREA_BOUNDS[args.area]
    # Latitude is descending (north→south), so slice high→low
    u_current_array = u_current_array.sel(
        latitude=slice(max_lat, min_lat),
        longitude=slice(min_lon, max_lon)
    )
    v_current_array = v_current_array.sel(
        latitude=slice(max_lat, min_lat),
        longitude=slice(min_lon, max_lon)
    )

    Ni, Nj, Nt = len(u_current_array.longitude), len(u_current_array.latitude), len(u_current_array.time)
    print(f"Cropped grid: {Ni} lon x {Nj} lat x {Nt} time steps")

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
    # Configure logging
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    args.output_dir = os.path.abspath(os.path.expanduser(args.output_dir))

    # Validate CLI values
    if not (1 <= args.days <= 10):
        logging.error("Invalid --days value %s: must be between 1 and 10", args.days)
        sys.exit(2)

    # Validate temporal resolution format (e.g. '15m', '1h')
    if not re.match(r"^\d+(m|h|d)$", args.temporal_resolution):
        logging.error("Invalid --temporal-resolution '%s'. Expected formats like '15m', '1h', '1d'", args.temporal_resolution)
        sys.exit(2)
    
    # Check output directory exists, if not create it
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        logging.info("Created output directory: %s", args.output_dir)

    # Set current working directory to the project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Check credentials (may raise on failure)
    try:
        check_credentials(args.credentials_dir)
    except Exception:
        logging.error("Unable to verify Copernicus Marine credentials; aborting.")
        sys.exit(1)

    try:
        current_forecast_list = download_files_using_subset(args)
    except Exception as e:
        logging.warning("Subset download failed: %s", e)
        logging.info("Falling back to file-based download...")
        current_forecast_list = download_files(args)

    u_current_array, v_current_array = collate_files(current_forecast_list, args)

    u_current_array, v_current_array = reduce_resolution(args, u_current_array, v_current_array)

    north_lat, south_lat, west_long, east_long = float(u_current_array.latitude[0]), float(u_current_array.latitude[-1]), float(u_current_array.longitude[0]), float(u_current_array.longitude[-1])
    Ni, Nj = len(u_current_array.longitude), len(u_current_array.latitude)
    di, dj = float(u_current_array.longitude[1] - u_current_array.longitude[0]), abs(float(u_current_array.latitude[1] - u_current_array.latitude[0]))
    logging.info("Area: %s, %s, %s, %s", north_lat, west_long, south_lat, east_long)

    grib_path = os.path.expanduser(os.path.join(args.output_dir, args.grib_filename))

    # Delete the GRIB file if it alreadyexists
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

    if args.delete_forecasts:
        # Delete the forecast NetCDF files
        for file in current_forecast_list:
            if os.path.exists(file):
                os.remove(file)
                logging.info("Deleted file: %s", file)
            else:
                logging.warning("File not found: %s", file)

if __name__ == "__main__":
    main()
