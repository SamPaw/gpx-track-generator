#  Fake Run GPX Generator

A Python tool to generate realistic running activities from any route GPX file. Perfect for generating believable GPS activities with natural pace variations and pauses for platforms like Strava and Garmin Connect.

---

##  How It Works

1. **Plan your route**: Create and download a route `.gpx` file from [gpx.studio](https://gpx.studio) (or export any route from Strava/Komoot).
2. **Run the script**: Launch `main.py` to enter your target route, desired start time, pace, and pause settings.
3. **Get your activity**: The tool calculates realistic second-by-second GPS coordinates with natural pace drift and stationary pauses, exporting a valid GPX 1.1 file ready to upload.

---

##  Getting Started

### Prerequisites

No external `pip` packages required! This project uses only the Python standard library.
- Python 3.10+

### Quick Start

1. Open your terminal and navigate to the project directory:
   ```bash
   cd /path/to/gpx_strava
   ```

2. Run the interactive interface:
   ```bash
   python main.py
   ```

3. Follow the on-screen prompts:
   - **Target GPX filename**: Path to your route file created from [gpx.studio](https://gpx.studio) (e.g. `route.gpx`).
   - **Output GPX filename**: Desired output filename (press Enter for default `<name>_fake.gpx`).
   - **Start date and time**: Timestamp of the run in `YYYY-MM-DD HH:MM` format (e.g. `2026-10-12 06:30`).
   - **Target pace**: Pace in minutes per kilometer (press Enter for default `6.0` min/km).
   - **Number of pauses**: Number of rest stops to simulate (press Enter for `0`).

---

##  Command-Line Usage (CLI Flags)

You can also bypass the prompts and pass arguments directly:

```bash
python main.py -t route.gpx -o morning_run.gpx -s "2026-10-12 06:30" -p 5.5 --stops 2
```

### Available Options

| Flag | Alternative | Description | Default |
| :--- | :--- | :--- | :--- |
| `-t`, `--target` | Position 1 | Path to input route GPX | *Prompted* |
| `-o`, `--out` | Position 2 | Destination GPX file path | `<target>_fake.gpx` |
| `-s`, `--start` | | Start time (`YYYY-MM-DD HH:MM` or ISO format) | *Prompted* |
| `-p`, `--pace` | | Average pace in `min/km` | `6.0` |
| `--stops` | `--pauses` | Number of pauses during the run | `0` |

---

##  Python API Usage

You can also import and use the simulation engine in your own scripts:

```python
from datetime import datetime, timezone
from fakerun import generate_fake_run

result = generate_fake_run(
    source_gpx="route.gpx",
    destination_gpx="my_run.gpx",
    start_time=datetime(2026, 10, 12, 6, 30, tzinfo=timezone.utc),
    pace_min_per_km=5.5,
    stops=1,
)

print(f"Generated {result.total_distance_km:.2f} km in {result.elapsed_time}!")
```

---

##  Project Architecture

- **`main.py`**: User interface handling interactive prompts, CLI arguments, input validation, and summary reporting.
- **`fakerun.py`**: Core simulation engine handling Haversine distance math, track interpolation, dynamic pace drift (85%–115%), and GPX 1.1 XML generation.

---

That's it — you can now fake your runs with realistic data!

**ALL THE BEST!** 🚀
