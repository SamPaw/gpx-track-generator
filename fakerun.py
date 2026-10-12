import argparse
import bisect
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

# Pre-declared defaults
DEFAULT_PACE_MIN_PER_KM = 6.0                                # default average pace (min/km)
DEFAULT_STOP_SECONDS = (40, 120)                             # duration range (seconds) for each pause if pauses > 0


def clean_path(path_str: str) -> str:
    """Clean quotation marks and extra whitespace from path input."""
    if not path_str:
        return ""
    path_str = path_str.strip()
    if (path_str.startswith('"') and path_str.endswith('"')) or (
        path_str.startswith("'") and path_str.endswith("'")
    ):
        path_str = path_str[1:-1].strip()
    return path_str


def parse_start_time(time_str: str) -> datetime:
    """Parse start date and time from user input into a UTC-aware datetime."""
    time_str = time_str.strip()
    # Try ISO-like parsing first
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

    # Try common user-friendly formats
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %I:%M%p",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    raise ValueError(
        "Unrecognized format. Please use 'YYYY-MM-DD HH:MM' (e.g. 2026-10-12 06:30)."
    )


def get_parameters():
    """Prompt user for target file, output file, start time, pace, and pauses (or read CLI flags)."""
    parser = argparse.ArgumentParser(
        description="Generate a realistic faked GPX running activity from a target route GPX."
    )
    parser.add_argument("src", nargs="?", help="Target GPX filename/path (input route)")
    parser.add_argument("dst", nargs="?", help="Output GPX filename/path")
    parser.add_argument("-t", "--target", dest="target_flag", help="Target GPX filename/path")
    parser.add_argument("-o", "--out", dest="out_flag", help="Output GPX filename/path")
    parser.add_argument("-s", "--start", dest="start_flag", help="Start date & time (e.g. '2026-10-12 06:30')")
    parser.add_argument("-p", "--pace", dest="pace_flag", type=float, help="Pace in min/km (default: 6.0)")
    parser.add_argument("--stops", "--pauses", dest="stops_flag", type=int, help="Number of pauses (default: 0)")
    args = parser.parse_args()

    # 1. Target file selection
    src = clean_path(args.target_flag or args.src)
    if not src:
        while True:
            try:
                user_src = input("Enter target GPX filename (input route): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nOperation cancelled.")
                sys.exit(0)

            user_src = clean_path(user_src)
            if not user_src:
                print("Error: Target filename cannot be empty. Please try again.")
                continue
            if not os.path.isfile(user_src):
                print(f"Error: Target file '{user_src}' not found. Please try again.")
                continue
            src = user_src
            break
    else:
        if not os.path.isfile(src):
            print(f"Error: Target file '{src}' does not exist.")
            sys.exit(1)

    # 2. Output file selection
    target_path = Path(src)
    default_dst_name = f"{target_path.stem}_fake.gpx"
    default_dst = target_path.with_name(default_dst_name)

    dst = clean_path(args.out_flag or args.dst)
    if not dst:
        try:
            prompt = f"Enter output GPX filename [default: {default_dst_name}]: "
            user_dst = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(0)

        user_dst = clean_path(user_dst)
        if not user_dst:
            dst = str(default_dst)
        else:
            dst_path = Path(user_dst)
            if not dst_path.suffix:
                dst_path = dst_path.with_suffix(".gpx")
            dst = str(dst_path)
    else:
        dst_path = Path(dst)
        if not dst_path.suffix:
            dst = str(dst_path.with_suffix(".gpx"))

    # 3. Start date and time (kept empty at first for user to enter)
    start_dt = None
    if args.start_flag:
        try:
            start_dt = parse_start_time(args.start_flag)
        except ValueError as e:
            print(f"Error in --start argument: {e}")
            sys.exit(1)
    else:
        while True:
            try:
                user_start = input("Enter start date and time (YYYY-MM-DD HH:MM): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nOperation cancelled.")
                sys.exit(0)

            if not user_start:
                print("Error: Start date and time is required. Example: 2026-10-12 06:30")
                continue

            try:
                start_dt = parse_start_time(user_start)
                break
            except ValueError as e:
                print(f"Error: {e}")

    # 4. Target pace (pre-declared default of 6.0, option for user to change)
    if args.pace_flag is not None:
        pace = float(args.pace_flag)
    else:
        while True:
            try:
                user_pace = input(f"Enter target pace in min/km [default: {DEFAULT_PACE_MIN_PER_KM}]: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nOperation cancelled.")
                sys.exit(0)

            if not user_pace:
                pace = DEFAULT_PACE_MIN_PER_KM
                break

            try:
                val = float(user_pace)
                if val <= 0:
                    print("Error: Pace must be greater than 0.")
                    continue
                pace = val
                break
            except ValueError:
                print("Error: Please enter a valid number for pace (e.g. 5.5).")

    # 5. Pauses (kept empty at first, if empty initialize as 0 pauses, else use value)
    if args.stops_flag is not None:
        stops = int(args.stops_flag)
    else:
        while True:
            try:
                user_stops = input("Enter number of pauses (leave empty for 0): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nOperation cancelled.")
                sys.exit(0)

            if not user_stops:
                stops = 0
                break

            try:
                val = int(user_stops)
                if val < 0:
                    print("Error: Number of pauses cannot be negative.")
                    continue
                stops = val
                break
            except ValueError:
                print("Error: Please enter a valid whole number for pauses.")

    return src, dst, start_dt, pace, stops


def dist(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def main():
    src, dst, start_dt, pace, stops = get_parameters()

    print(f"\n--- Simulation Settings ---")
    print(f"Target Route File: {src}")
    print(f"Output GPX File  : {dst}")
    print(f"Start Time (UTC) : {start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Target Pace      : {pace:.2f} min/km")
    print(f"Number of Pauses : {stops}")
    print(f"---------------------------")

    try:
        root = ET.parse(src).getroot()
    except Exception as e:
        print(f"Error reading GPX XML from '{src}': {e}")
        sys.exit(1)

    pts = [
        (float(p.get("lat")), float(p.get("lon")))
        for p in root.iter()
        if p.tag.endswith("trkpt") or p.tag.endswith("rtept")
    ]

    if len(pts) < 2:
        print(f"Error: Found {len(pts)} track/route points in '{src}'. At least 2 points are required.")
        sys.exit(1)

    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + dist(pts[i - 1], pts[i]))
    total = cum[-1]

    def at(d):
        i = min(bisect.bisect_right(cum, d) - 1, len(pts) - 2)
        seg = cum[i + 1] - cum[i]
        f = 0 if seg == 0 else (d - cum[i]) / seg
        return (
            pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f,
            pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f,
        )

    stop_at = (
        sorted(random.uniform(0.1, 0.9) * total for _ in range(stops))
        if stops > 0
        else []
    )
    base = 1000 / (pace * 60)      # metres per second
    d, t, drift, out = 0.0, start_dt, 1.0, []

    while d < total:
        out.append((t, at(d)))
        if stop_at and d >= stop_at[0]:
            stop_at.pop(0)
            for _ in range(random.randint(*DEFAULT_STOP_SECONDS)):
                t += timedelta(seconds=1)
                out.append((t, at(d)))        # same position, clock keeps running
        drift = max(0.85, min(1.15, drift + random.uniform(-0.03, 0.03)))
        d += base * drift
        t += timedelta(seconds=1)
    out.append((t, pts[-1]))

    # Use output filename (cleaned) for GPX track name for documentation in Strava
    activity_name = Path(dst).stem.replace("_", " ").replace("-", " ").title()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="manual" xmlns="http://www.topografix.com/GPX/1/1">',
        f'<trk><name>{activity_name}</name><trkseg>',
    ]
    for ts, (la, lo) in out:
        lines.append(
            f'<trkpt lat="{la:.6f}" lon="{lo:.6f}"><time>{ts.strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>'
        )
    lines += ['</trkseg></trk></gpx>']

    # Ensure target output directory exists if specified
    out_dir = Path(dst).parent
    if out_dir and not out_dir.exists():
        out_dir.mkdir(parents=True, exist_ok=True)

    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nSuccessfully generated '{dst}'!")
    print(f"Track Name : {activity_name}")
    print(f"Distance   : {total / 1000:.2f} km")
    print(f"Elapsed    : {t - start_dt}")
    print(f"Total Pts  : {len(out)}")


if __name__ == "__main__":
    main()