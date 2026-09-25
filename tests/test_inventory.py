"""Behavioral tests for the inventory model and its command-line interface."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.cli import read_asset
from src.inventory import Asset, Inventory, format_report


ROOT = Path(__file__).resolve().parents[1]


def workstation(**changes):
    values = {
        "asset_id": "A101",
        "name": "HR-PC-01",
        "asset_type": "Workstation",
        "ip_address": "192.168.1.10",
        "operating_system": "Windows 11",
        "department": "HR",
        "risk_level": "Medium",
        "security_status": "Secure",
    }
    values.update(changes)
    return Asset(**values)


def sample_assets():
    return [
        workstation(),
        workstation(
            asset_id="A102",
            name="Web-Server",
            asset_type="Server",
            ip_address="192.168.1.20",
            operating_system="Ubuntu",
            department="IT",
            risk_level="Critical",
            security_status="Vulnerable",
        ),
        workstation(
            asset_id="A103",
            name="Core-Router",
            asset_type="Router",
            ip_address="192.168.1.1",
            operating_system="Cisco IOS",
            department="Network",
            risk_level="High",
            security_status="Warning",
        ),
    ]


def batch_input(assets):
    lines = [str(len(assets))]
    for asset in assets:
        lines.extend(
            getattr(asset, field)
            for field in (
                "asset_id", "name", "asset_type", "ip_address",
                "operating_system", "department", "risk_level", "security_status",
            )
        )
    return "\n".join(lines) + "\n"


class AssetValidationTests(unittest.TestCase):
    def test_whitespace_and_category_case_are_normalized(self):
        asset = workstation(
            asset_id=" A101 ", name=" HR-PC-01 ", asset_type=" workstation ",
            ip_address=" 192.168.1.10 ", operating_system=" Windows 11 ",
            department=" HR ", risk_level=" mEdIuM ", security_status=" SECURE ",
        )
        self.assertEqual(asset, workstation())

    def test_every_field_is_required(self):
        for field in (
            "asset_id", "name", "asset_type", "ip_address", "operating_system",
            "department", "risk_level", "security_status",
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                workstation(**{field: "   "})

    def test_invalid_categories_and_ip_are_rejected(self):
        for field, value in (
            ("asset_type", "Printer"), ("risk_level", "Extreme"),
            ("security_status", "Patched"), ("ip_address", "999.1.2.3"),
            ("ip_address", "example.com"), ("ip_address", "192.168.1.10/24"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                workstation(**{field: value})

    def test_switch_application_and_ipv6_are_supported(self):
        self.assertEqual(workstation(asset_type="switch").asset_type, "Switch")
        self.assertEqual(workstation(asset_type="application").asset_type, "Application")
        self.assertEqual(workstation(ip_address="2001:db8::1").ip_address, "2001:db8::1")


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.inventory = Inventory(sample_assets())

    def test_ids_are_case_insensitive_and_unique(self):
        self.assertEqual(self.inventory.get("a101").name, "HR-PC-01")
        with self.assertRaises(ValueError):
            self.inventory.add(workstation(asset_id="a101"))
        self.assertEqual(len(self.inventory.assets), 3)

    def test_duplicate_initial_assets_are_rejected(self):
        with self.assertRaises(ValueError):
            Inventory([workstation(), workstation(asset_id="a101")])

    def test_search_matches_multiple_fields_case_insensitively(self):
        for query, expected in (
            ("web", ["A102"]), ("cisco", ["A103"]),
            ("vulnerable", ["A102"]), ("192.168.1.", ["A101", "A102", "A103"]),
            ("hR", ["A101"]), ("not-present", []),
        ):
            with self.subTest(query=query):
                self.assertEqual([a.asset_id for a in self.inventory.search(query)], expected)

    def test_update_changes_values_and_recalculates_summary(self):
        updated = self.inventory.update("a101", risk_level="critical", security_status="vulnerable")
        self.assertEqual(updated.risk_level, "Critical")
        self.assertEqual(updated.security_status, "Vulnerable")
        self.assertEqual(self.inventory.get("A101"), updated)
        self.assertEqual(self.inventory.summary(), {
            "total": 3, "critical": 2, "high": 1, "medium": 0, "vulnerable": 2,
        })

    def test_invalid_update_is_atomic(self):
        with self.assertRaises(ValueError):
            self.inventory.update("A101", name="Changed", risk_level="invalid")
        self.assertEqual(self.inventory.get("A101"), workstation())

    def test_unknown_fields_and_duplicate_id_updates_are_rejected(self):
        with self.assertRaises(ValueError):
            self.inventory.update("A101", unexpected="value")
        with self.assertRaises(ValueError):
            self.inventory.update("A101", asset_id="a102")
        self.assertEqual(self.inventory.get("A101"), workstation())
        self.assertEqual(len(self.inventory.assets), 3)

    def test_id_can_be_renamed(self):
        updated = self.inventory.update("A101", asset_id="A201")
        self.assertEqual(updated.asset_id, "A201")
        self.assertEqual(self.inventory.get("a201").name, "HR-PC-01")
        with self.assertRaises(ValueError):
            self.inventory.get("A101")

    def test_delete_returns_asset_and_removes_it(self):
        self.assertEqual(self.inventory.delete("a101"), workstation())
        self.assertEqual(len(self.inventory.assets), 2)
        with self.assertRaises(ValueError):
            self.inventory.get("A101")

    def test_missing_id_operations_fail(self):
        for operation in (self.inventory.get, self.inventory.delete, self.inventory.update):
            with self.subTest(operation=operation.__name__), self.assertRaises(ValueError):
                operation("missing")

    def test_assets_property_does_not_expose_internal_list(self):
        copy = self.inventory.assets
        copy.clear()
        self.assertEqual(len(self.inventory.assets), 3)

    def test_summaries_include_zero_counts(self):
        self.assertEqual(self.inventory.summary(), {
            "total": 3, "critical": 1, "high": 1, "medium": 1, "vulnerable": 1,
        })
        self.assertEqual(Inventory().summary(), {
            "total": 0, "critical": 0, "high": 0, "medium": 0, "vulnerable": 0,
        })

    def test_json_round_trip_preserves_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            self.inventory.save(path)
            json.loads(path.read_text(encoding="utf-8"))
            restored = Inventory.load(path)
            self.assertEqual(restored.assets, self.inventory.assets)
            self.assertEqual(restored.summary(), self.inventory.summary())

    def test_missing_or_corrupt_storage_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            with self.assertRaises((ValueError, OSError)):
                Inventory.load(path)
            path.write_text("{broken JSON", encoding="utf-8")
            with self.assertRaises((ValueError, OSError)):
                Inventory.load(path)

    def test_report_contains_all_asset_values_and_expected_counts(self):
        report = format_report(self.inventory.assets)
        for value in (
            "A101", "HR-PC-01", "192.168.1.10", "Windows 11", "HR",
            "A102", "Web-Server", "192.168.1.20", "Ubuntu", "IT",
            "A103", "Core-Router", "192.168.1.1", "Cisco IOS", "Network",
            "Workstation", "Server", "Router", "Medium", "Critical", "High",
            "Secure", "Vulnerable", "Warning",
        ):
            with self.subTest(value=value):
                self.assertIn(value, report)
        for label, count in (
            ("Total Assets", 3), ("Critical Assets", 1), ("High Risk Assets", 1),
            ("Medium Risk Assets", 1), ("Vulnerable Assets", 1),
        ):
            with self.subTest(label=label):
                self.assertRegex(report, rf"{label}\s*:\s*{count}\b")


class InteractiveInputTests(unittest.TestCase):
    def test_field_entry_and_update_do_not_print_choice_lists(self):
        for current in (None, workstation()):
            with self.subTest(updating=current is not None):
                values = [""] * 8 if current else batch_input([workstation()]).splitlines()[1:]
                inventory = Inventory([current]) if current else Inventory()
                output = StringIO()
                with (
                    patch("src.cli.sys.stdin.isatty", return_value=True),
                    patch("builtins.input", side_effect=values) as user_input,
                    redirect_stdout(output),
                ):
                    asset = read_asset(inventory, current)
                self.assertEqual(asset, workstation())
                prompts = "\n".join(call.args[0] for call in user_input.call_args_list)
                visible_text = output.getvalue() + prompts
                self.assertIn("Asset Type", prompts)
                self.assertIn("Risk Level", prompts)
                self.assertIn("Security Status", prompts)
                self.assertNotIn("Options:", visible_text)
                self.assertNotIn("Workstation, Server, Router", visible_text)
                self.assertNotIn("Low, Medium, High, Critical", visible_text)
                self.assertNotIn("Secure, Warning, Vulnerable", visible_text)


class CommandLineTests(unittest.TestCase):
    def run_cli(self, *args, input_text="", cwd=ROOT):
        return subprocess.run(
            [sys.executable, str(ROOT / "main.py"), *args],
            input=input_text, text=True, capture_output=True, cwd=cwd, timeout=10,
        )

    def test_batch_input_produces_sample_report(self):
        result = self.run_cli(input_text=batch_input(sample_assets()))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HR-PC-01", result.stdout)
        self.assertIn("Web-Server", result.stdout)
        self.assertIn("Core-Router", result.stdout)
        self.assertRegex(result.stdout, r"Total Assets\s*:\s*3\b")
        self.assertNotIn("Enter number of assets", result.stdout)

    def test_invalid_count_reprompts_and_valid_input_succeeds(self):
        result = self.run_cli(input_text="many\n-1\n" + batch_input([workstation()]))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HR-PC-01", result.stdout)
        self.assertRegex(result.stdout, r"Total Assets\s*:\s*1\b")

    def test_invalid_field_reprompts(self):
        values = "1\nA101\nHR-PC-01\nWorkstation\ninvalid-ip\n192.168.1.10\nWindows 11\nHR\nMedium\nSecure\n"
        result = self.run_cli(input_text=values)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("192.168.1.10", result.stdout)
        self.assertNotIn("invalid-ip", result.stdout)

    def test_eof_does_not_persist_a_partial_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            existing = Inventory([workstation(asset_id="EXISTING")])
            existing.save(path)
            original = path.read_bytes()
            first_complete = batch_input([workstation()]).split("\n", 1)[1]
            result = self.run_cli("--data", str(path), input_text="2\n" + first_complete + "A102\n")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(path.read_bytes(), original)

    def test_storage_opt_in_can_be_loaded_for_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            saved = self.run_cli("--data", str(path), input_text=batch_input(sample_assets()))
            self.assertEqual(saved.returncode, 0, saved.stderr)
            result = self.run_cli("--report", "--data", str(path))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Web-Server", result.stdout)
            self.assertRegex(result.stdout, r"Total Assets\s*:\s*3\b")

    def test_default_run_does_not_create_data_files(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(input_text=batch_input([workstation()]), cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_demo_outputs_sample_without_input(self):
        result = self.run_cli("--demo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Web-Server", result.stdout)
        self.assertRegex(result.stdout, r"Total Assets\s*:\s*3\b")

    def test_report_requires_storage_path(self):
        result = self.run_cli("--report")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--data", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_menu_add_search_delete_and_exit(self):
        entries = "1\n" + batch_input([workstation()]) + "3\nHR-PC-01\n5\nA101\ny\n6\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            result = self.run_cli("--menu", "--data", str(path), input_text=entries)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("HR-PC-01", result.stdout)
            self.assertEqual(Inventory.load(path).assets, [])

    def test_menu_add_collects_requested_assets_and_saves_all(self):
        entries = "1\n" + batch_input(sample_assets()) + "2\n6\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            result = self.run_cli("--menu", "--data", str(path), input_text=entries)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Enter number of assets:", result.stderr)
            self.assertIn("HR-PC-01", result.stdout)
            self.assertIn("Web-Server", result.stdout)
            self.assertIn("Core-Router", result.stdout)
            self.assertRegex(result.stdout, r"Total Assets\s*:\s*3\b")
            self.assertEqual(Inventory.load(path).assets, sample_assets())

    def test_menu_add_reprompts_for_invalid_count(self):
        entries = "1\nmany\n-1\n" + batch_input([workstation()]) + "2\n6\n"
        result = self.run_cli("--menu", input_text=entries)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.count("Enter number of assets:"), 3)
        self.assertIn("HR-PC-01", result.stdout)
        self.assertRegex(result.stdout, r"Total Assets\s*:\s*1\b")

    def test_menu_add_zero_assets_returns_without_creating_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            result = self.run_cli("--menu", "--data", str(path), input_text="1\n0\n2\n6\n")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertRegex(result.stdout, r"Total Assets\s*:\s*0\b")
            self.assertFalse(path.exists())

    def test_interrupted_menu_add_does_not_save_partial_group(self):
        first_complete = batch_input([workstation()]).split("\n", 1)[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            Inventory([workstation(asset_id="EXISTING")]).save(path)
            original = path.read_bytes()
            result = self.run_cli(
                "--menu", "--data", str(path), input_text="1\n2\n" + first_complete + "A102\n",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(path.read_bytes(), original)

    def test_menu_update_keeps_blank_fields_and_saves_changes(self):
        entries = "\n".join([
            "4", "A101", "A201", "", "", "", "", "", "High", "Warning", "6",
        ]) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            Inventory([workstation()]).save(path)
            result = self.run_cli("--menu", "--data", str(path), input_text=entries)
            self.assertEqual(result.returncode, 0, result.stderr)
            restored = Inventory.load(path)
            self.assertEqual(restored.get("A201"), workstation(
                asset_id="A201", risk_level="High", security_status="Warning",
            ))
            with self.assertRaises(ValueError):
                restored.get("A101")

    def test_menu_matches_requested_options_and_rejects_zero(self):
        expected_menu = (
            "1. Add Asset\n"
            "2. Display All Assets\n"
            "3. Search Asset\n"
            "4. Update Asset\n"
            "5. Delete Asset\n"
            "6. Exit"
        )
        result = self.run_cli("--menu", input_text="0\n6\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout + result.stderr
        self.assertEqual(output.count(expected_menu), 2)
        self.assertIn("Invalid option", output)
        self.assertNotIn("CYBERSECURITY ASSET INVENTORY - MENU", output)

    def test_src_entrypoint_opens_menu_without_creating_data(self):
        source_directory = ROOT / "src"
        data_before = set(source_directory.rglob("*.json"))
        result = subprocess.run(
            [sys.executable, "asset_inventory.py"],
            input="6\n", text=True, capture_output=True, cwd=source_directory, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = result.stdout + result.stderr
        self.assertIn("1. Add Asset", output)
        self.assertIn("6. Exit", output)
        self.assertNotIn("Enter number of assets", output)
        self.assertEqual(set(source_directory.rglob("*.json")), data_before)

    @unittest.skipUnless(sys.platform == "win32", "Windows launcher")
    def test_windows_launcher_preserves_program_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_path = str(Path(directory) / "missing.json")
            for args, expected in (
                (["--demo"], 0),
                (["--unknown-option"], 2),
                (["--report", "--data", missing_path], 1),
            ):
                with self.subTest(args=args):
                    result = subprocess.run(
                        ["cmd.exe", "/d", "/c", "run.cmd", *args],
                        input="", text=True, capture_output=True, cwd=ROOT, timeout=10,
                    )
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
