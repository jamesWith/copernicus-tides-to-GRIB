# 🌊 Tide Current Converter

This project downloads high-resolution tidal current forecast data from the **Copernicus Marine Service**, converts the U/V vector components to knots (from m/s), and exports the result to a valid **GRIB2** file. It is designed for use in marine navigation systems and chartplotters.

---

## 📦 Cloning the Repository

Clone the repository using:

```bash
git clone https://github.com/jamesWith/tide-current-converter.git
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

Run the tide converter script via Poetry:

```bash
poetry run python Copernicus-tides-to-GRIB.py
```

By default, it will:
- Download the dataset `cmems_mod_nws_phy_anfc_0.027deg-2D_PT15M-i` for the **next 10 days**
- Compute speed (knots) and bearing (degrees from north) from U/V current components
- Save the result to a GRIB2 file named `tidal_currents.grib2`

---

## 🧾 Input & Output

### 📥 Input
- **Dataset:** `cmems_mod_nws_phy_anfc_0.027deg-2D_PT15M-i`
- **Resolution:** 0.027°, every 15 minutes
- **Variables:** `uo` (eastward), `vo` (northward)

### 📤 Output
- `tidal_currents.grib2`
  - 2D grid of **current speed in knots** and **bearing in degrees**
  - One GRIB message per field per time step
  - Correctly georeferenced with `regular_ll` grid type

---

## 📚 Dependencies

This project uses the following Python libraries:

- `copernicusmarine`
- `xarray`
- `numpy`
- `pandas`
- `scipy`
- `cfgrib`
- `eccodes`
- `pyproj`
- `climetlab`
- `pygrib` (optional)
- `cdsapi` (unused currently)

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

- [ ] Parameterize time window and spatial bounding box via CLI flags
- [ ] Add support for vertical layers (e.g., depth-specific currents)
- [ ] Add unit tests for speed/bearing calculation
- [ ] Write GRIB2 using pure `eccodes` instead of climetlab
- [ ] Dockerize the tool for portable deployment
- [ ] Optionally export to NetCDF, CSV, or GeoTIFF
- [ ] Add command-line interface or GUI

---

## 🙏 Acknowledgments

- [Copernicus Marine Service (CMEMS)](https://marine.copernicus.eu/)
- [ECMWF ecCodes](https://confluence.ecmwf.int/display/ECC/ecCodes+Home)
- [xarray](https://docs.xarray.dev/)
- [Python Poetry](https://python-poetry.org/)

---

## 📄 License

This project is licensed under the MIT License. See [`LICENSE`](./LICENSE) for details.
