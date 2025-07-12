# CMAM - Connor Merk App Manager
# Package manager for installing and managing Connor Merk's applications.
# Copyright (c) 2025 Connor Merk

# --------------------------------------
# TODO:
#   - Implement actual installation logic.
#   - Integrate with GitHub for app manifests.
#   - Add error handling and logging.
#   - Support for uninstalling applications.
#   - Enhance user interface with Rich for better UX.
#   - Add more commands (list, update, remove).
#   - Config file for user preferences.
#   - Implement self-update/version check.
# --------------------------------------

import os
import sys
import winreg
import requests
import json
import base64
import typer
import hashlib
import ctypes
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()
app = typer.Typer(
    help="CMAM: Connor Merk App Manager - Your package manager for Connor Merk's apps.",
    no_args_is_help=True
)

# ═══════════════════════════════════════
# PATH HANDLING
# ═══════════════════════════════════════

def add_folder_to_path(folder_path: str) -> bool:
    """
    Adds a specified folder to the user's PATH on Windows.
    """
    folder_path = os.path.abspath(folder_path)

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)

        try:
            current_path, reg_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""
            reg_type = winreg.REG_EXPAND_SZ

        path_separator = ';'
        paths = [p.strip() for p in current_path.split(path_separator) if p.strip()]

        if folder_path.lower() in [os.path.normpath(p).lower() for p in paths]:
            console.print(f"[yellow]'{folder_path}' is already in the User PATH.[/yellow]")
            winreg.CloseKey(key)
            return True

        new_path = f"{current_path}{path_separator}{folder_path}" if current_path else folder_path
        winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
        winreg.CloseKey(key)

        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, 0
        )

        console.print(f"[bold green]Successfully added '{folder_path}' to User PATH.[/bold green]")
        console.print("[yellow]Note: Restart terminal or log off/on for changes to apply.[/yellow]")
        return True

    except Exception as e:
        console.print(f"[bold red]Error modifying PATH: {e}[/bold red]")
        return False

# ═══════════════════════════════════════
# INSTALL COMMAND
# ═══════════════════════════════════════

@app.command()
def install(
    app_name: str = typer.Argument(..., help="Name of the application to install."),
    version: str = typer.Option(None, "--version", "-v", help="Specify a version to install.")
):
    """
    Installs a specified application from the CMAM repository.
    """
    console.print(
        f"[bold cyan]Initiating installation for [green]{app_name}[/green]"
        + (f" (version [magenta]{version}[/magenta])" if version else "")
        + "...[/bold cyan]"
    )

    status = console.status("[bold green]Getting ready...[/bold green]")
    status.start()

    # -----------------------------------
    # CREATE REQUIRED FOLDERS
    # -----------------------------------
    for folder in [r"C:\\.cmam", r"C:\\.cmam\.cache", r"C:\\.cmam\scripts"]:
        os.makedirs(folder, exist_ok=True)

    packages_file = r"C:\\.cmam\packages.txt"
    if not os.path.exists(packages_file):
        open(packages_file, 'w').close()

    # -----------------------------------
    # FETCH APP MANIFEST
    # -----------------------------------
    status.update("[bold green]Fetching application manifest...[/bold green]")
    request_url = "https://api.github.com/repos/cmerk2021/cmam/contents/packages.json"

    try:
        response = requests.get(request_url)
        response.raise_for_status()
        manifest_data = response.json()

        if manifest_data.get('type') == 'file' and 'content' in manifest_data:
            decoded = base64.b64decode(manifest_data['content']).decode('utf-8')
            app_data = json.loads(decoded)

            if app_data.get(app_name) is None:
                status.stop()
                console.print(f"[bold red]App [blue]{app_name}[/blue] not found in manifest.[/bold red]")
                raise typer.Exit(code=1)

            app_data = app_data[app_name]

        else:
            status.stop()
            console.print("[bold red]Error: Invalid or missing 'packages.json' in GitHub repo.[/bold red]")
            raise typer.Exit(code=1)

    except requests.RequestException as e:
        status.stop()
        console.print(f"[bold red]Network error while fetching manifest: {e}[/bold red]")
        raise typer.Exit(code=1)
    except json.JSONDecodeError:
        status.stop()
        console.print("[bold red]Error parsing 'packages.json'.[/bold red]")
        raise typer.Exit(code=1)

    # -----------------------------------
    # DOWNLOAD BINARY
    # -----------------------------------
    status.update("[bold green]Downloading application...[/bold green]")
    app_link = app_data["link"]

    api_url = (
        f"https://api.github.com/repos/{app_link}/releases/latest"
        if not version else
        f"https://api.github.com/repos/{app_link}/releases/tags/v{version}"
    )

    response = requests.get(api_url)
    response.raise_for_status()
    release_data = response.json()

    exe_url = None
    exe_filename = None
    checksum = None

    for asset in release_data.get('assets', []):
        if asset.get('name', '').lower().endswith('.exe'):
            exe_url = asset.get('browser_download_url')
            checksum = asset.get("digest")
            exe_filename = asset['name']
            break

    if not exe_url:
        status.stop()
        console.print("[bold red]Error: No .exe asset found in release.[/bold red]")
        raise typer.Exit(code=1)

    exe_response = requests.get(exe_url)
    exe_response.raise_for_status()

    # -----------------------------------
    # VERIFY CHECKSUM
    # -----------------------------------
    status.update("[bold green]Verifying checksum...[/bold green]")

    if not checksum:
        console.print("[bold yellow]Warning: No checksum provided. Skipping verification.[/bold yellow]")
    else:
        sha256 = hashlib.sha256(exe_response.content).hexdigest()
        if f"sha256:{sha256}" != checksum:
            status.stop()
            console.print("[bold red]ERROR: Checksum mismatch. Aborting install.[/bold red]")
            raise typer.Exit(code=1)

    # -----------------------------------
    # WRITE EXECUTABLE TO DISK
    # -----------------------------------
    status.update("[bold green]Installing application...[/bold green]")

    try:
        exe_path = fr"C:\\.cmam\scripts\{app_name}.exe"
        with open(exe_path, 'wb') as f:
            f.write(exe_response.content)
    except Exception as e:
        status.stop()
        console.print(f"[bold red]Installation failed: {e}[/bold red]")
        raise typer.Exit(code=1)

    # -----------------------------------
    # UPDATE PATH
    # -----------------------------------
    status.update("[bold green]Finalizing PATH...[/bold green]")
    add_folder_to_path(r"C:\\.cmam\scripts")

    # ✅ FINISH
    status.stop()
    console.print(Panel(
        "[bold green]Installation successful![/bold green]\n\n"
        "You can now run your new app.",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))
    console.print("[yellow]Reminder: Restart terminal for new PATH changes to be recognized.[/yellow]")

# ═══════════════════════════════════════
# DUMMY COMMAND FOR TESTING
# ═══════════════════════════════════════

@app.command()
def hello():
    """Says hello. Placeholder command."""
    console.print("[green]Hello from CMAM![/green]")

# ═══════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════

if __name__ == "__main__":
    app()
