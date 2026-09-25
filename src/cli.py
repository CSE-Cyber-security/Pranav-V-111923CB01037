"""Input prompts and the main menu."""

import argparse
from dataclasses import asdict
from pathlib import Path
import sys

from .inventory import Asset, FIELD_LABELS, Inventory, format_report, validate_field


def prompt(message):
    # Keep prompts out of the report when output is redirected.
    if sys.stdin.isatty():
        return input(message)
    print(message, end="", file=sys.stderr, flush=True)
    return input()


def progress(message):
    print(message, file=sys.stdout if sys.stdin.isatty() else sys.stderr)


def read_asset(inventory, current=None):
    values = {}
    if current:
        progress("Press Enter to keep the current value.")
    for field, label in FIELD_LABELS.items():
        suffix = f" [{getattr(current, field)}]" if current else ""
        while True:
            raw = prompt(f"{label}{suffix}: ")
            if current and not raw.strip():
                raw = getattr(current, field)
            try:
                value = validate_field(field, raw)
                if field == "asset_id":
                    for asset in inventory.assets:
                        if asset is current:
                            continue
                        if asset.asset_id.casefold() == value.casefold():
                            raise ValueError(f"Asset ID '{value}' already exists.")
            except ValueError as error:
                progress(f"Error: {error}")
                continue
            values[field] = value
            break
    return Asset(**values)


def read_count():
    while True:
        try:
            count = int(prompt("Enter number of assets: ").strip())
            if count < 0:
                raise ValueError
            return count
        except ValueError:
            progress("Error: enter a whole number of assets (0 or greater).")


def read_assets(inventory):
    count = read_count()
    for index in range(1, count + 1):
        progress(f"\nAsset {index}")
        inventory.add(read_asset(inventory))
    return count


def run_batch(inventory, data_path):
    read_assets(inventory)
    if data_path:
        inventory.save(data_path)
    print(format_report(inventory.assets))


def run_menu(inventory, data_path):
    while True:
        progress(
            "\n1. Add Asset\n2. Display All Assets\n3. Search Asset\n"
            "4. Update Asset\n5. Delete Asset\n6. Exit"
        )
        choice = prompt("Choose an option: ").strip()
        if choice == "6":
            progress("Goodbye.")
            return
        try:
            if choice == "2":
                print(format_report(inventory.assets))
                continue
            if choice == "3":
                query = prompt("Search ID, name, type, IP, OS, department, risk, or status: ").strip()
                if not query:
                    progress("Enter a search term.")
                    continue
                matches = inventory.search(query)
                progress(f"Matches: {len(matches)}. The summary below counts these results.")
                print(format_report(matches))
                continue
            # Work on a copy in case saving fails.
            candidate = Inventory(inventory.assets)
            if choice == "1":
                count = read_assets(candidate)
                if count == 0:
                    progress("No assets added.")
                    continue
                message = "1 asset added." if count == 1 else f"{count} assets added."
            elif choice == "4":
                current = candidate.get(prompt("Asset ID to update: "))
                updated = read_asset(candidate, current)
                candidate.update(current.asset_id, **asdict(updated))
                message = f"Asset '{updated.asset_id}' updated."
            elif choice == "5":
                asset = candidate.get(prompt("Asset ID to delete: "))
                answer = prompt(f"Delete '{asset.asset_id}' ({asset.name})? [y/N]: ")
                if answer.strip().casefold() not in ("y", "yes"):
                    progress("Deletion cancelled.")
                    continue
                candidate.delete(asset.asset_id)
                message = f"Asset '{asset.asset_id}' deleted."
            else:
                progress("Invalid option. Choose 1, 2, 3, 4, 5, or 6.")
                continue
            if data_path:
                candidate.save(data_path)
            inventory = candidate
            progress(message)
        except (ValueError, OSError) as error:
            progress(f"Error: {error}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cybersecurity Asset Inventory System")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--menu", action="store_true", help="add, display, search, update, and delete assets")
    mode.add_argument("--demo", action="store_true", help="show the sample report")
    mode.add_argument("--report", action="store_true", help="print saved assets from --data without prompting")
    parser.add_argument("--data", type=Path, metavar="FILE", help="load and save inventory as JSON (optional)")
    args = parser.parse_args(argv)
    if args.report and not args.data:
        parser.error("--report requires --data FILE")
    if args.demo and args.data:
        parser.error("--demo cannot be combined with --data")
    try:
        if args.demo:
            sample_path = Path(__file__).resolve().parent.parent / "data" / "sample_assets.json"
            print(format_report(Inventory.load(sample_path).assets))
            return 0
        inventory = Inventory()
        if args.data:
            try:
                inventory = Inventory.load(args.data)
            except FileNotFoundError:
                if args.report:
                    raise
        if args.report:
            print(format_report(inventory.assets))
        elif args.menu:
            run_menu(inventory, args.data)
        else:
            run_batch(inventory, args.data)
        return 0
    except EOFError:
        print("\nInput ended before the operation was complete. Incomplete changes were not saved.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled. Incomplete changes were not saved.", file=sys.stderr)
        return 130
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
