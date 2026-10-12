"""main.py - User Interface and Entry Point for Fake Run GPX Generator.

This script acts as the main user interface. It handles:
  1. Interactive terminal prompts for all simulation parameters.
  2. Optional command-line argument parsing (flags and positional args).
  3. Input sanitization (stripping surrounding quotes, path validation).
  4. Datetime parsing with timezone normalization (UTC).
  5. Delegating the actual simulation and file export to fakerun.py.
  6. Presenting clean summary documentation upon completion.

Usage:
  Interactive Mode:
    python main.py

  CLI Mode:
    python main.py -t route.gpx -o my_run.gpx -s "2026-10-12 06:30" -p 5.5 --stops 2
"""

from datetime import datetime, timezone
from pathlib import Path
import argparse
import os
import sys

from fakerun import (
    DEFAULT_PACE_MIN_PER_KM,
    SimulationResult,
    generate_fake_run,
)


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
    """Parse start date and time from user input into a UTC-aware datetime.

    Accepts ISO formats (e.g. 2026-10-12T06:30:00) and standard date/time strings
    (e.g. '2026-10-12 06:30', '12-10-2026 06:30').
    """
    time_str = time_str.strip()
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

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
        "Unrecognized format. Please enter date and time as 'YYYY-MM-DD HH:MM' (e.g. 2026-10-12 06:30)."
    )


def prompt_target_file(initial_value: str | None = None) -> str:
    """Interactively prompt user for the target route GPX file."""
    src = clean_path(initial_value) if initial_value else ""
    if src:
        if not os.path.isfile(src):
            print(f"Error: Target file '{src}' does not exist.")
            sys.exit(1)
        return src

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
        return user_src


def prompt_output_file(src_path: str, initial_value: str | None = None) -> str:
    """Interactively prompt user for the output GPX file name with a default."""
    target_path = Path(src_path)
    default_dst_name = f"{target_path.stem}_fake.gpx"
    default_dst = target_path.with_name(default_dst_name)

    dst = clean_path(initial_value) if initial_value else ""
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

    return dst


def prompt_start_time(initial_value: str | None = None) -> datetime:
    """Interactively prompt user for start date and time."""
    if initial_value:
        try:
            return parse_start_time(initial_value)
        except ValueError as e:
            print(f"Error in --start argument: {e}")
            sys.exit(1)

    while True:
        try:
            user_start = input("Enter start date and time[in UTC] (YYYY-MM-DD HH:MM): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(0)

        if not user_start:
            print("Error: Start date and time is required (e.g. 2026-10-12 06:30).")
            continue

        try:
            return parse_start_time(user_start)
        except ValueError as e:
            print(f"Error: {e}")


def prompt_pace(initial_value: float | None = None) -> float:
    """Interactively prompt user for running pace, defaulting to 6.0 min/km."""
    if initial_value is not None:
        return float(initial_value)

    while True:
        try:
            prompt = f"Enter target pace in min/km [default: {DEFAULT_PACE_MIN_PER_KM}]: "
            user_pace = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(0)

        if not user_pace:
            return DEFAULT_PACE_MIN_PER_KM

        try:
            pace = float(user_pace)
            if pace <= 0:
                print("Error: Pace must be greater than 0.")
                continue
            return pace
        except ValueError:
            print("Error: Please enter a valid number for pace (e.g. 5.5).")


def prompt_stops(initial_value: int | None = None) -> int:
    """Interactively prompt user for pause count, defaulting to 0."""
    if initial_value is not None:
        return int(initial_value)

    while True:
        try:
            user_stops = input("Enter number of pauses (leave empty for 0): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            sys.exit(0)

        if not user_stops:
            return 0

        try:
            stops = int(user_stops)
            if stops < 0:
                print("Error: Number of pauses cannot be negative.")
                continue
            return stops
        except ValueError:
            print("Error: Please enter a valid whole number for pauses (e.g. 2).")


def parse_arguments():
    """Parse optional command-line flags and arguments."""
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
    return parser.parse_args()


def main():
    """Main execution flow coordinating user input, simulation, and summary reporting."""
    args = parse_arguments()

    # Step 1: Target route file
    target_file = prompt_target_file(args.target_flag or args.src)

    # Step 2: Output file name
    output_file = prompt_output_file(target_file, args.out_flag or args.dst)

    # Step 3: Start date and time
    start_dt = prompt_start_time(args.start_flag)

    # Step 4: Pace (min/km)
    pace = prompt_pace(args.pace_flag)

    # Step 5: Pauses / Stops
    stops = prompt_stops(args.stops_flag)

    print("\n--- Simulation Settings ---")
    print(f"Target Route File: {target_file}")
    print(f"Output GPX File  : {output_file}")
    print(f"Start Time (UTC) : {start_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Target Pace      : {pace:.2f} min/km")
    print(f"Number of Pauses : {stops}")
    print("---------------------------")

    try:
        result: SimulationResult = generate_fake_run(
            source_gpx=target_file,
            destination_gpx=output_file,
            start_time=start_dt,
            pace_min_per_km=pace,
            stops=stops,
        )
    except Exception as exc:
        print(f"\nSimulation Failed: {exc}")
        sys.exit(1)

    print(f"\nSuccessfully generated '{result.output_path}'!")
    print(f"Track Name : {result.activity_name}")
    print(f"Distance   : {result.total_distance_km:.2f} km")
    print(f"Elapsed    : {result.elapsed_time}")
    print(f"Total Pts  : {result.total_points}")


if __name__ == "__main__":
    main()
