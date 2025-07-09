# 🌊 Tide Current Converter

This project downloads high-resolution tidal current forecast data from the **Copernicus Marine Service**, converts the U/V vector components to knots (from m/s), and exports the result to a valid **GRIB2** file. While designed to help route plotting it should not be relied upon for navigation, double check the data before using it for any critical applications.

All credit for the data used goes to [Copernicus Marine Service (CMEMS)](https://marine.copernicus.eu/).

---

## 📦 Cloning the Repository

Clone the repository using:

```bash
git clone https://github.com/jamesWith/copernicus-tides-to-GRIB.git
cd tide-current-converter
```

---

## 🐍 Installing Python (if needed)

This project uses **Python version 3.11 and up** . To install:

### Option 1: Install Python 3.11 or higher directly
- **Linux:** Use your package manager (e.g., `sudo apt install python`)
- **macOS:** Use [Homebrew](https://brew.sh/):
  ```bash
  brew install python
  ```
- **Windows:** Download from [python.org](https://www.python.org/downloads/)

Ensure the version is 3.11 or higher when downloading.
### Option 2: Use `pyenv` to manage Python versions
If you prefer to manage Python versions easily, install pyenv using their [handy installation instructions.](https://github.com/pyenv/pyenv#installation) This includes a link to install a pyenv for windows too.

---

## 🛠 Project Setup (Poetry)

Make sure Poetry is installed on your system. Poetry is a dependency management tool for Python that simplifies package installation and virtual environment management. Installation instructions can be found on their [official documentation](https://python-poetry.org/docs/#installation) for macOS, Linux and Windows.

Then set up the environment and install dependencies:

```bash
poetry install
```

---

## 🔐 Setting Up Copernicus Marine Credentials

If you don't have a Copernicus Marine account, you can register for free at [Copernicus Marine Service](https://data.marine.copernicus.eu/register).

The first time you run the script, you will need to authenticate with your Copernicus Marine credentials. This is required to access the datasets. The program will detect if you do not have a credentials file and prompt you to log in with your username  and password. *(Note that your username isnt necessarily the same as your email address, see the email they sent you or the webpage once logged in to see your username. Often it is [first letter of first name] + [last name])* 

This will create a credentials file at `~/.copernicusmarine/.copernicusmarine-credentials`
The script will then use this to authenticate future requests so you should only need to log in once.

---

## 🚀 Usage

After downloading the repository and installing dependencies, you can run the script using Poetry:

```bash
poetry run tideconvert [OPTIONS]
```

### 🔧 Command-line Options

| Flag / Option                  | Description |
|-------------------------------|-------------|
| `-t`, `--temporal-resolution` | Time between data points. Accepts multiples of 15 minutes such as `'15m'`, `'30m'`, `'1h'`, `'6h'`, etc.<br>**Default:** `15m` |
| `-s`, `--spatial-resolution-factor` | Integer factor to reduce spatial resolution. Use `2` to skip every other lat/lon point, `3` to skip every two, etc.<br>**Default:** `1` (full resolution) |
| `-d`, `--days`                | Number of forecast days to download (**1–10**).<br>**Default:** `5` |
| `-i`, `--dataset-id`          | Dataset ID to download from Copernicus Marine. Override this if using a different product.<br>**Default:** `cmems_mod_nws_phy_anfc_0.027deg-2D_PT15M-i` |
| `-l`, `--low-data`            | Enable low-data mode to reduce bandwidth usage and only download new forecasts.<br>**Note:** _Not yet implemented_ |
| `-o`, `--output-dir`          | Directory to save downloaded forecasts and GRIB output.<br>**Default:** current working directory |
| `-g`, `--grib-filename`       | Filename for the output GRIB2 file.<br>**Default:** `tidal_currents.grib2` |
| `-c`, `--credentials-dir`     | Directory where `.copernicusmarine/` credentials are stored. Used to authenticate with CMEMS.<br>**Default:** `~` (user home) |
| `-k`, `--keep-forecasts`      | Retain forecast NetCDF files after conversion to GRIB.<br>**Note:** _In low data mode only forecasts in the past are deleted to save redownloading them._ <br>**Default:** _Files are deleted after use_ |
| `-v`, `--verbose`             | Enable verbose/debug output.<br>**Note:** _Not yet implemented_ |

---

### ✅ Example

```bash
tideconvert \
  --days 3 \
  --temporal-resolution 30m \
  --spatial-resolution-factor 2 \
  --output-dir ./data \
  --grib-filename mycurrents.grib2 \
  --keep-forecasts
```

This example downloads 3 days of data at 30-minute intervals, skips every other grid point, writes output to `./data/mycurrents.grib2`, and keeps all downloaded NetCDF files.
```


---

## 📚 Dependencies

This project uses the following Python libraries:

- `os`
- `argparse`
- `xarray`
- `datetime`
- `copernicusmarine`
- `eccodes`

To see all versions, check [`pyproject.toml`](./pyproject.toml).

### 🛠 System Dependencies

You must also install the **ecCodes** system library:

#### Debian/Ubuntu:
```bash
sudo apt install libeccodes-tools
```

#### macOS (Homebrew):
```bash
brew install eccodes
```

---

## 🧠 Future Work / TODO

- [ ] Enable support for low-data mode to reduce bandwidth usage.
- [ ] Implement verbose/debug output.
- [ ] Enable useage with other Copernicus Marine datasets.

---

## 🙏 Acknowledgments

- [Copernicus Marine Service (CMEMS)](https://marine.copernicus.eu/)
- [ECMWF ecCodes](https://confluence.ecmwf.int/display/ECC/ecCodes+Home)
- [xarray](https://docs.xarray.dev/)
- [Python Poetry](https://python-poetry.org/)

---

## 📄 License

This project is licensed under the GPL-3 License. See [`LICENSE`](./LICENSE) for details.
