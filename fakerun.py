"""fakerun.py - Core GPX Running Simulation Engine.

This module contains the actual working logic for:
  1. Parsing GPX route tracks and extracting GPS coordinates.
  2. Great-circle distance calculations using the Haversine formula.
  3. Continuous spatial interpolation along multi-point routes.
  4. Realistic running simulation with pace drift and optional pauses.
  5. GPX 1.1 XML generation compatible with Strava, Garmin, and others.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import bisect
import math
import os
from pathlib import Path
import random
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Default Configuration Constants
# ---------------------------------------------------------------------------
DEFAULT_PACE_MIN_PER_KM: float = 6.0                 # Default target pace: 6.0 min/km
DEFAULT_STOP_SECONDS: tuple[int, int] = (40, 120)    # Duration range (seconds) for each pause
EARTH_RADIUS_METERS: float = 6371000.0               # Mean radius of the Earth in meters


@dataclass
class SimulationResult:
    """Summary of the generated GPX run activity."""
    output_path: Path
    activity_name: str
    total_distance_km: float
    elapsed_time: timedelta
    total_points: int
    start_time: datetime
    pace_min_per_km: float
    stops_count: int


def haversine_distance(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """Calculate the great-circle distance between two points on Earth in meters.

    Parameters:
        coord1: (latitude, longitude) of point 1 in degrees.
        coord2: (latitude, longitude) of point 2 in degrees.

    Returns:
        Distance in meters.
    """
    lat1, lon1, lat2, lon2 = map(math.radians, (coord1[0], coord1[1], coord2[0], coord2[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_METERS * c


def parse_gpx_points(gpx_path: str | Path) -> list[tuple[float, float]]:
    """Parse track or route points from an input GPX file.

    Parameters:
        gpx_path: Path to the input GPX file.

    Returns:
        List of (latitude, longitude) tuples.

    Raises:
        FileNotFoundError: If the input file does not exist.
        ET.ParseError: If the GPX file contains invalid XML.
        ValueError: If fewer than 2 coordinates are found in the GPX file.
    """
    path_obj = Path(gpx_path)
    if not path_obj.is_file():
        raise FileNotFoundError(f"Target GPX file not found: {gpx_path}")

    root = ET.parse(path_obj).getroot()
    points = [
        (float(p.get("lat")), float(p.get("lon")))
        for p in root.iter()
        if p.tag.endswith("trkpt") or p.tag.endswith("rtept")
    ]

    if len(points) < 2:
        raise ValueError(
            f"GPX file '{gpx_path}' contains {len(points)} points. At least 2 points are required."
        )

    return points


def interpolate_coordinate(
    points: list[tuple[float, float]],
    cumulative_distances: list[float],
    target_distance: float,
) -> tuple[float, float]:
    """Calculate the exact (latitude, longitude) at a target distance along the track.

    Uses binary search (`bisect_right`) to locate the relevant segment, followed by
    linear interpolation between the segment's two endpoints.

    Parameters:
        points: Ordered list of track (lat, lon) coordinates.
        cumulative_distances: Cumulative distance in meters from the start to each point.
        target_distance: Traveled distance along the route in meters.

    Returns:
        Interpolated (latitude, longitude) tuple.
    """
    idx = min(bisect.bisect_right(cumulative_distances, target_distance) - 1, len(points) - 2)
    seg_length = cumulative_distances[idx + 1] - cumulative_distances[idx]

    factor = 0.0 if seg_length == 0 else (target_distance - cumulative_distances[idx]) / seg_length
    lat = points[idx][0] + (points[idx + 1][0] - points[idx][0]) * factor
    lon = points[idx][1] + (points[idx + 1][1] - points[idx][1]) * factor
    return lat, lon


def simulate_run(
    points: list[tuple[float, float]],
    start_time: datetime,
    pace_min_per_km: float = DEFAULT_PACE_MIN_PER_KM,
    stops: int = 0,
    stop_seconds_range: tuple[int, int] = DEFAULT_STOP_SECONDS,
) -> tuple[list[tuple[datetime, tuple[float, float]]], float, timedelta]:
    """Simulate a realistic running track with natural pace drift and optional pauses.

    Simulation characteristics:
      - Pace drift: Speed dynamically drifts smoothly between 85% and 115% of base speed,
        mimicking human surges, elevation changes, and fatigue.
      - Pauses: If stops > 0, pause checkpoints are randomly distributed along the route.
        During each pause, the runner stays stationary while time advances second-by-second.

    Parameters:
        points: List of route coordinates (lat, lon).
        start_time: Activity start timestamp (UTC-aware).
        pace_min_per_km: Target average pace in minutes per kilometer.
        stops: Number of pauses during the run (0 for none).
        stop_seconds_range: (min, max) duration range in seconds for each pause.

    Returns:
        A tuple of:
          - List of track points: [(timestamp, (lat, lon)), ...]
          - Total route distance in meters.
          - Total elapsed activity duration.
    """
    # 1. Build cumulative distance array
    cum_dist = [0.0]
    for i in range(1, len(points)):
        cum_dist.append(cum_dist[-1] + haversine_distance(points[i - 1], points[i]))
    total_dist = cum_dist[-1]

    # 2. Randomly select pause milestones (between 10% and 90% of total distance)
    stop_milestones = (
        sorted(random.uniform(0.1, 0.9) * total_dist for _ in range(stops))
        if stops > 0
        else []
    )

    # 3. Base speed in meters per second
    base_speed = 1000.0 / (pace_min_per_km * 60.0)

    # 4. Simulation loop
    current_dist = 0.0
    current_time = start_time
    pace_drift = 1.0
    track_records: list[tuple[datetime, tuple[float, float]]] = []

    while current_dist < total_dist:
        coord = interpolate_coordinate(points, cum_dist, current_dist)
        track_records.append((current_time, coord))

        # Check for pause event
        if stop_milestones and current_dist >= stop_milestones[0]:
            stop_milestones.pop(0)
            pause_duration = random.randint(*stop_seconds_range)
            for _ in range(pause_duration):
                current_time += timedelta(seconds=1)
                track_records.append((current_time, coord))

        # Update speed drift with small random step, bounded between 0.85 and 1.15
        pace_drift = max(0.85, min(1.15, pace_drift + random.uniform(-0.03, 0.03)))
        current_dist += base_speed * pace_drift
        current_time += timedelta(seconds=1)

    # Ensure final coordinate is explicitly recorded
    track_records.append((current_time, points[-1]))
    elapsed_duration = current_time - start_time

    return track_records, total_dist, elapsed_duration


def export_gpx(
    track_records: list[tuple[datetime, tuple[float, float]]],
    output_path: str | Path,
    activity_name: str,
) -> Path:
    """Format and write simulated track records to a GPX 1.1 file.

    Parameters:
        track_records: List of (timestamp, (latitude, longitude)) records.
        output_path: Destination file path.
        activity_name: Track name embedded inside the <trk><name> GPX tag.

    Returns:
        Path object pointing to the written GPX file.
    """
    dest = Path(output_path)
    if dest.parent and not dest.parent.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="fakerun" xmlns="http://www.topografix.com/GPX/1/1">',
        f'<trk><name>{activity_name}</name><trkseg>',
    ]

    for ts, (lat, lon) in track_records:
        utc_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"><time>{utc_str}</time></trkpt>')

    lines.append('</trkseg></trk></gpx>')

    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return dest


def generate_fake_run(
    source_gpx: str | Path,
    destination_gpx: str | Path,
    start_time: datetime,
    pace_min_per_km: float = DEFAULT_PACE_MIN_PER_KM,
    stops: int = 0,
    activity_name: str | None = None,
) -> SimulationResult:
    """High-level entry point to execute the GPX fake run simulation.

    Parameters:
        source_gpx: Path to the template route GPX file.
        destination_gpx: Path where the generated GPX file will be saved.
        start_time: Starting timestamp (UTC-aware).
        pace_min_per_km: Target running pace in min/km.
        stops: Number of pauses during the run.
        activity_name: Optional custom track name. Defaults to a title-cased
                       version of the destination filename stem.

    Returns:
        SimulationResult containing activity statistics and file path.
    """
    dest_path = Path(destination_gpx)
    if not activity_name:
        activity_name = dest_path.stem.replace("_", " ").replace("-", " ").title()

    points = parse_gpx_points(source_gpx)
    track_records, total_meters, elapsed_time = simulate_run(
        points=points,
        start_time=start_time,
        pace_min_per_km=pace_min_per_km,
        stops=stops,
    )

    written_path = export_gpx(
        track_records=track_records,
        output_path=dest_path,
        activity_name=activity_name,
    )

    return SimulationResult(
        output_path=written_path,
        activity_name=activity_name,
        total_distance_km=total_meters / 1000.0,
        elapsed_time=elapsed_time,
        total_points=len(track_records),
        start_time=start_time,
        pace_min_per_km=pace_min_per_km,
        stops_count=stops,
    )


# ---------------------------------------------------------------------------
# Direct Execution Support
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # If run directly as a script, forward to main.py's user interface
    from main import main
    main()