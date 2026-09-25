"""Asset records and inventory operations."""

from dataclasses import asdict, dataclass, fields, replace
from ipaddress import ip_address
import json
import os
from pathlib import Path
import tempfile


ASSET_TYPES = ("Workstation", "Server", "Router", "Switch", "Application")
RISK_LEVELS = ("Low", "Medium", "High", "Critical")
SECURITY_STATUSES = ("Secure", "Warning", "Vulnerable")
FIELD_LABELS = {
    "asset_id": "Asset ID",
    "name": "Asset Name",
    "asset_type": "Asset Type",
    "ip_address": "IP Address",
    "operating_system": "Operating System",
    "department": "Department",
    "risk_level": "Risk Level",
    "security_status": "Security Status",
}
CHOICES = {
    "asset_type": ASSET_TYPES,
    "risk_level": RISK_LEVELS,
    "security_status": SECURITY_STATUSES,
}


def validate_field(field, value):
    if field not in FIELD_LABELS:
        raise ValueError(f"Unknown asset field: {field}")
    label = FIELD_LABELS[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} cannot be empty and must be text.")
    value = value.strip()
    if not value.isprintable():
        raise ValueError(f"{label} must not contain control characters.")
    if field in CHOICES:
        for option in CHOICES[field]:
            if value.casefold() == option.casefold():
                return option
        raise ValueError(f"{label} must be one of: {', '.join(CHOICES[field])}.")
    if field == "ip_address":
        try:
            ip_address(value)
        except ValueError:
            raise ValueError("IP Address must be a valid IPv4 or IPv6 address.") from None
    return value


@dataclass(frozen=True)
class Asset:
    asset_id: str
    name: str
    asset_type: str
    ip_address: str
    operating_system: str
    department: str
    risk_level: str
    security_status: str

    def __post_init__(self):
        for field in fields(self):
            value = validate_field(field.name, getattr(self, field.name))
            object.__setattr__(self, field.name, value)


class Inventory:
    def __init__(self, assets=()):
        self._assets = {}
        for asset in assets:
            self.add(asset)

    @property
    def assets(self):
        return list(self._assets.values())

    def add(self, asset):
        if not isinstance(asset, Asset):
            raise ValueError("Inventory entries must be Asset objects.")
        key = asset.asset_id.casefold()
        if key in self._assets:
            raise ValueError(f"Asset ID '{asset.asset_id}' already exists.")
        self._assets[key] = asset

    def get(self, asset_id):
        key = validate_field("asset_id", asset_id).casefold()
        if key not in self._assets:
            raise ValueError(f"Asset ID '{asset_id.strip()}' was not found.")
        return self._assets[key]

    def search(self, query):
        query = query.strip().casefold()
        matches = []
        for asset in self._assets.values():
            for value in asdict(asset).values():
                if query in value.casefold():
                    matches.append(asset)
                    break
        return matches

    def update(self, target_id, **changes):
        original = self.get(target_id)
        unknown = changes.keys() - FIELD_LABELS.keys()
        if unknown:
            raise ValueError(f"Unknown asset field: {', '.join(sorted(unknown))}")
        updated = replace(original, **changes)
        old_key = original.asset_id.casefold()
        new_key = updated.asset_id.casefold()
        if new_key != old_key and new_key in self._assets:
            raise ValueError(f"Asset ID '{updated.asset_id}' already exists.")
        # Keep the asset in the same position if its ID changes.
        records = {}
        for key, asset in self._assets.items():
            if key == old_key:
                records[new_key] = updated
            else:
                records[key] = asset
        self._assets = records
        return updated

    def delete(self, asset_id):
        asset = self.get(asset_id)
        del self._assets[asset.asset_id.casefold()]
        return asset

    def summary(self):
        counts = {
            "total": len(self._assets),
            "critical": 0,
            "high": 0,
            "medium": 0,
            "vulnerable": 0,
        }
        for asset in self._assets.values():
            if asset.risk_level == "Critical":
                counts["critical"] += 1
            elif asset.risk_level == "High":
                counts["high"] += 1
            elif asset.risk_level == "Medium":
                counts["medium"] += 1
            if asset.security_status == "Vulnerable":
                counts["vulnerable"] += 1
        return counts

    def save(self, path):
        """Write to a temporary file first so a failed save keeps the old data."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                json.dump([asdict(asset) for asset in self.assets], stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

    @classmethod
    def load(cls, path):
        try:
            with Path(path).open(encoding="utf-8-sig") as stream:
                records = json.load(stream)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise ValueError(f"Invalid inventory file: {error}") from None
        if not isinstance(records, list):
            raise ValueError("Invalid inventory file: expected a JSON list of assets.")
        inventory = cls()
        for index, record in enumerate(records, 1):
            if not isinstance(record, dict) or record.keys() != FIELD_LABELS.keys():
                raise ValueError(f"Invalid inventory file: asset {index} must contain all eight asset fields.")
            try:
                inventory.add(Asset(**record))
            except ValueError as error:
                raise ValueError(f"Invalid inventory file, asset {index}: {error}") from None
        return inventory


def format_report(assets):
    inventory = Inventory(assets)
    border = "=" * 41
    lines = [border, "CYBERSECURITY ASSET INVENTORY".center(41).rstrip(), border]
    report_fields = dict(FIELD_LABELS, operating_system="OS", security_status="Status")
    for index, asset in enumerate(inventory.assets):
        if index:
            lines.append("-" * 41)
        for field, label in report_fields.items():
            lines.append(f"{label:<13} : {getattr(asset, field)}")
    if not inventory.assets:
        lines.append("No assets in the inventory.")
    lines.append(border)
    summary = inventory.summary()
    for key, label in (
        ("total", "Total Assets"), ("critical", "Critical Assets"),
        ("high", "High Risk Assets"), ("medium", "Medium Risk Assets"),
        ("vulnerable", "Vulnerable Assets"),
    ):
        lines.append(f"{label:<18} : {summary[key]}")
    lines.append(border)
    return "\n".join(lines)
