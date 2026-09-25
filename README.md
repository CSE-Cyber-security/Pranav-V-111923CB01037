# Week 01 – Cybersecurity Asset Inventory System

A command-line Python program that lets a security administrator **add, search, update, delete, and display** an organization's IT assets. Each record includes its asset type, security risk level, and current security status.

## Problem Statement

Organizations manage many IT assets, including computers, servers, routers, switches, and software applications. Tracking them manually makes it difficult to keep records up to date and identify assets that need attention. This program keeps those details in one place and provides a simple menu for managing them.

## Features

- **Add Asset** – enter how many assets you want to add, then provide each asset's ID, Name, Type, IP Address, Operating System, Department, Risk Level, and Security Status. Checks for duplicate IDs, empty fields, and invalid IP addresses.
- **Display All Assets** – show every asset in a report, followed by total, critical, high-risk, medium-risk, and vulnerable asset counts.
- **Search Asset** – find assets by ID, name, type, IP address, OS, department, risk level, or status. Searches are case-insensitive.
- **Update Asset** – edit any field of an existing asset. Leave a field blank to keep its current value.
- **Delete Asset** – remove an asset after confirming the deletion.
- **Persistence** – use `--data data/inventory.json` to save completed changes and load the same records on the next run. Without `--data`, records last only for the current session.

## Data Fields

| Field | Allowed Values |
| --- | --- |
| Asset Type | Workstation, Server, Router, Switch, Application |
| Risk Level | Low, Medium, High, Critical |
| Security Status | Secure, Warning, Vulnerable |

The program uses the risk level and security status entered by the user. The vulnerable count is based on security status, independently of risk level.

## How to Run

From the project folder:

```bash
cd src
python3 asset_inventory.py
```

On Windows, open PowerShell in the project folder and run:

```powershell
.\run.cmd --menu
```

You'll see a menu:

```text
1. Add Asset
2. Display All Assets
3. Search Asset
4. Update Asset
5. Delete Asset
6. Exit
```

Enter a number to choose an action, then follow the prompts.

Choosing **1. Add Asset** first asks `Enter number of assets:`. Enter the count, then type the details for Asset 1, Asset 2, and so on. Fields use plain prompts such as `Asset Type:` without displaying option lists. Enter `0` at the count prompt to return to the menu.

To save changes between runs, use `python3 asset_inventory.py --data ../data/inventory.json` from `src`, or `.\run.cmd --menu --data .\data\inventory.json` from the project folder in PowerShell. Without `--data`, records last only for the current session.

When adding several assets, the group is saved after all entries are complete. If input is interrupted, that group is not saved.

To enter the number of assets first and print a report after entering their details, run this from the project folder:

```bash
python main.py
```

## Sample Output

From the project folder, use the assignment's three sample assets in PowerShell:

```powershell
Get-Content .\data\sample_input.txt | .\run.cmd
```

You can also run `python main.py --demo` to display this report:

```text
=========================================
      CYBERSECURITY ASSET INVENTORY
=========================================
Asset ID      : A101
Asset Name    : HR-PC-01
Asset Type    : Workstation
IP Address    : 192.168.1.10
OS            : Windows 11
Department    : HR
Risk Level    : Medium
Status        : Secure
-----------------------------------------
Asset ID      : A102
Asset Name    : Web-Server
Asset Type    : Server
IP Address    : 192.168.1.20
OS            : Ubuntu
Department    : IT
Risk Level    : Critical
Status        : Vulnerable
-----------------------------------------
Asset ID      : A103
Asset Name    : Core-Router
Asset Type    : Router
IP Address    : 192.168.1.1
OS            : Cisco IOS
Department    : Network
Risk Level    : High
Status        : Warning
=========================================
Total Assets       : 3
Critical Assets    : 1
High Risk Assets   : 1
Medium Risk Assets : 1
Vulnerable Assets  : 1
=========================================
```

## Tech Used

- Python 3.8 or later.
- Standard library modules, including `json`, `os`, `dataclasses`, `ipaddress`, and `argparse`.
- JSON files for storing asset records.
- No external dependencies required.

To run the tests:

```bash
python -m unittest discover -s tests -v
```
