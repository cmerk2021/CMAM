# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  CMAM - Connor Merk App Manager                                            ║
# ║  Package manager for installing and managing Connor Merk's applications.   ║
# ║  Copyright (c) 2026 Connor Merk                                            ║
# ║  VERSION: 1.5.0                                                            ║
# ╚════════════════════════════════════════════════════════════════════════════╝

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  IMPORTS                                                                   ║
# ╚════════════════════════════════════════════════════════════════════════════╝

import os
import sys
import json
import base64
import hashlib
import shutil
import ctypes
import winreg
import requests
from requests.exceptions import HTTPError
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TimeRemainingColumn

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  CONSTANTS & GLOBALS                                                       ║
# ╚════════════════════════════════════════════════════════════════════════════╝

CMAM_ROOT = r"C:\\.cmam"
CMAM_CACHE = os.path.join(CMAM_ROOT, ".cache")
CMAM_SCRIPTS = os.path.join(CMAM_ROOT, "scripts")
CMAM_PACKAGES_JSON = os.path.join(CMAM_ROOT, "packages.json")
CMAM_PACKAGES_TXT = os.path.join(CMAM_ROOT, "packages.txt")
GITHUB_MANIFEST_URL = "https://api.github.com/repos/cmerk2021/cmam/contents/packages.json"

console = Console()
app = typer.Typer(
    help="CMAM: Connor Merk App Manager - Your package manager for Connor Merk's apps.",
    no_args_is_help=True
)
already_in_path = False

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  UTILITY FUNCTIONS                                                         ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def parse_version(v: str):
    """Parse a version string into a comparable tuple, handling pre-releases."""
    import re

    v = v.strip("v")
    match = re.match(r"(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9]+))?", v)
    if not match:
        raise ValueError(f"Invalid version format: {v}")

    major, minor, patch, pre = match.groups()
    version_tuple = (int(major), int(minor), int(patch))

    # Pre-release precedence (lower = earlier)
    pre_map = {
        None: 3,         # final release has highest precedence
        "rc": 2,
        "beta": 1,
        "alpha": 0
    }

    pre_key = pre_map.get(pre.lower(), -1) if pre else pre_map[None]

    return version_tuple + (pre_key,)

def print_banner():
    """Prints the CMAM startup banner."""
    console.print(
        Panel(
            "[bold blue]CMAM[/bold blue] [white]v1.5.0[/white]\n"
            "[green]Connor Merk App Manager[/green]\n"
            "[dim]https://github.com/cmerk2021/cmam[/dim]",
            border_style="blue",
            expand=False
        )
    )

def ensure_dirs():
    """Ensure all required directories exist."""
    for folder in [CMAM_ROOT, CMAM_CACHE, CMAM_SCRIPTS]:
        os.makedirs(folder, exist_ok=True)

def load_local_packages():
    """Load the local packages.json file."""
    try:
        with open(CMAM_PACKAGES_JSON, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_local_packages(data):
    """Save the local packages.json file."""
    with open(CMAM_PACKAGES_JSON, "w") as f:
        json.dump(data, f, indent=2)

def fetch_manifest():
    """Fetch and decode the remote app manifest."""
    try:
        response = requests.get(GITHUB_MANIFEST_URL)
        response.raise_for_status()
        manifest_data = response.json()
        if manifest_data.get('type') == 'file' and 'content' in manifest_data:
            decoded = base64.b64decode(manifest_data['content']).decode('utf-8')
            return json.loads(decoded)
        else:
            console.print("[bold red]❌ Invalid or missing 'packages.json' in GitHub repo.[/bold red]")
            raise typer.Exit(code=1)
    except requests.RequestException as e:
        console.print(f"[bold red]🌐 Network error: {e}[/bold red]")
        raise typer.Exit(code=1)
    except json.JSONDecodeError:
        console.print("[bold red]❌ Error parsing 'packages.json'.[/bold red]")
        raise typer.Exit(code=1)

def add_folder_to_path(folder_path: str) -> bool:
    """Add a folder to the user's PATH if not already present."""
    folder_path = os.path.abspath(folder_path)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
        try:
            current_path, reg_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""
            reg_type = winreg.REG_EXPAND_SZ

        paths = [p.strip() for p in current_path.split(';') if p.strip()]
        if folder_path.lower() in [os.path.normpath(p).lower() for p in paths]:
            winreg.CloseKey(key)
            global already_in_path 
            already_in_path = True
            return True

        new_path = f"{current_path};{folder_path}" if current_path else folder_path
        winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
        winreg.CloseKey(key)

        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, 0)

        console.print(f"[bold green]Successfully added '{folder_path}' to User PATH.[/bold green]")
        return True

    except Exception as e:
        console.print(f"[bold red]Error modifying PATH: {e}[/bold red]")
        return False

def not_implemented_message(command: str):
    """Show a consistent message for unimplemented commands."""
    console.print(f"[yellow]⚠ The '{command}' command is not yet implemented. Stay tuned![/yellow]")

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  MAIN COMMANDS                                                             ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.command()
def install(
    app_name: str = typer.Argument(..., help="Name of the application to install."),
    version: str = typer.Option(None, "--version", "-v", help="Specify a version to install.")
):
    """Installs a specified application from the CMAM repository."""

    print_banner()
    console.print(f"[bold cyan]🔧 Installing [green]{app_name}[/green]"
                  + (f" [magenta](v{version})[/magenta]" if version else "") + "...[/bold cyan]")

    with console.status("[bold green]Preparing installation...[/bold green]") as status:
        if os.path.exists(os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")):
            console.print(f"[bold red]⚠ App [blue]{app_name}[/blue] is already installed. Use [bold blue]update[/bold blue] instead.[/bold red]")
            raise typer.Exit(code=1)

        ensure_dirs()
        if not os.path.exists(CMAM_PACKAGES_TXT):
            open(CMAM_PACKAGES_TXT, 'w').close()

        # Fetch application manifest
        status.update("[bold green]Fetching application manifest...[/bold green]")
        app_manifest = fetch_manifest()
        if app_name not in app_manifest:
            console.print(f"[bold red]❌ App [blue]{app_name}[/blue] not found in manifest.[/bold red]")
            raise typer.Exit(code=1)
        app_data = app_manifest[app_name]

        # Download binary
        status.update("[bold green]Downloading application...[/bold green]")
        app_link = app_data["link"]
        api_url = f"https://api.github.com/repos/{app_link}/releases/latest" if not version else f"https://api.github.com/repos/{app_link}/releases/tags/v{version}"

        try:
            response = requests.get(api_url)
            response.raise_for_status()
        except HTTPError as e:
            if response.status_code == 404:
                console.print(f"[bold red]❌ Version '{version}' not found for this application.[/bold red]")
            else:
                console.print(f"[bold red]❌ HTTP error: {e}[/bold red]")
            raise typer.Exit(code=1)
        except requests.RequestException as e:
            console.print(f"[bold red]🌐 Network error: {e}[/bold red]")
            raise typer.Exit(code=1)

        release_data = response.json()
        exe_url, checksum, exe_filename = None, None, None
        app_version = release_data.get("tag_name")

        for asset in release_data.get('assets', []):
            if asset.get('name', '').lower().endswith('.exe'):
                exe_url = asset.get('browser_download_url')
                checksum = asset.get("digest")
                exe_filename = asset['name']
                break

        if not exe_url:
            console.print("[bold red]❌ No .exe asset found in release.[/bold red]")
            raise typer.Exit(code=1)

        tmp_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe.tmp")
        exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")

        status.stop()
        try:
            sha256 = hashlib.sha256()
            with requests.get(exe_url, stream=True) as r:
                r.raise_for_status()
                total = int(r.headers.get('Content-Length', 0))
                with open(tmp_path, 'wb') as f, Progress(
                    SpinnerColumn(),
                    TextColumn("{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TimeRemainingColumn(),
                    transient=True,
                ) as progress:
                    task = progress.add_task("[cyan]Downloading...", total=total)
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            sha256.update(chunk)
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))

            if checksum:
                if f"sha256:{sha256.hexdigest()}" != checksum:
                    console.print("[bold red]❌ Checksum mismatch. Aborting install.[/bold red]")
                    os.remove(tmp_path)
                    raise typer.Exit(code=1)
            else:
                console.print("[bold yellow]⚠ No checksum provided. Skipping verification.[/bold yellow]")

            os.replace(tmp_path, exe_path)

        except Exception as e:
            console.print(f"[bold red]❌ Failed to download or verify: {e}[/bold red]")
            raise typer.Exit(code=1)

        # Update PATH
        status.start()
        status.update("[bold green]Finalizing PATH...[/bold green]")
        add_folder_to_path(CMAM_SCRIPTS)

        # Update local package record
        status.update("[bold green]Saving metadata...[/bold green]")
        data = load_local_packages()
        data[app_name] = {"version": app_version.replace("v", "")}
        save_local_packages(data)

    # Completion
    console.print(Panel(
        f"[bold green]✅ {app_name} v{app_version.replace('v','')} installed successfully![/bold green]\n\n"
        "You can now run your app from any terminal window.",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))
    if not already_in_path:
        console.print("[yellow]💡 Tip: Restart your terminal to apply PATH changes.[/yellow]")

@app.command()
def update(
    app_name: str = typer.Argument(..., help="Name of the app to update."),
    version: str = typer.Option(None, "--version", "-v", help="Specify a version to update to."),
    keep_backup: bool = typer.Option(False, "--keep-backup", "-k", help="Keep backup of the old binary."),
):
    """Updates an application from the CMAM repository."""

    print_banner()
    console.print(f"[bold cyan]🔧 Updating [green]{app_name}[/green]"
                  + (f" [magenta](v{version})[/magenta]" if version else "") + "...[/bold cyan]")

    exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
    if not os.path.exists(exe_path):
        console.print(f"[bold red]⚠ App [blue]{app_name}[/blue] is not installed. Use [bold blue]install[/bold blue] instead.[/bold red]")
        raise typer.Exit(code=1)

    backup_dir = os.path.join(CMAM_CACHE, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"{app_name}.exe.bak")

    with console.status("[bold green]Preparing update...[/bold green]") as status:
        status.update("[bold green]Fetching application manifest...[/bold green]")
        app_manifest = fetch_manifest()
        if app_name not in app_manifest:
            console.print(f"[bold red]❌ App [blue]{app_name}[/blue] not found in manifest.[/bold red]")
            raise typer.Exit(code=1)
        app_data = app_manifest[app_name]

        # Determine current version
        data = load_local_packages()
        current_version = data.get(app_name, {}).get("version", "unknown")

        # Download release info
        app_link = app_data["link"]
        api_url = f"https://api.github.com/repos/{app_link}/releases/latest" if not version else f"https://api.github.com/repos/{app_link}/releases/tags/v{version}"
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            release_data = response.json()
        except HTTPError as e:
            if response.status_code == 404:
                console.print(f"[bold red]❌ Version '{version}' not found for this application.[/bold red]")
            else:
                console.print(f"[bold red]❌ HTTP error: {e}[/bold red]")
            raise typer.Exit(code=1)
        except requests.RequestException as e:
            console.print(f"[bold red]🌐 Network error: {e}[/bold red]")
            raise typer.Exit(code=1)

        new_version = release_data.get("tag_name", "").lstrip("v")
        if version and new_version != version:
            console.print(f"[bold red]❌ Version mismatch. Expected v{version}, got v{new_version}[/bold red]")
            raise typer.Exit(code=1)
        if current_version == new_version:
            console.print(f"[bold red]⚠ App [blue]{app_name}[/blue] is already at version [magenta]{new_version}[/magenta]. No update needed.[/bold red]")
            raise typer.Exit(code=1)

        # Find download asset
        exe_url, checksum, exe_filename = None, None, None
        for asset in release_data.get('assets', []):
            if asset.get('name', '').lower().endswith('.exe'):
                exe_url = asset.get('browser_download_url')
                checksum = asset.get("digest")
                exe_filename = asset['name']
                break

        if not exe_url:
            console.print("[bold red]❌ No .exe asset found in release.[/bold red]")
            raise typer.Exit(code=1)

        tmp_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe.tmp")

        status.update("[bold green]Backing up old binary...[/bold green]")
        shutil.copy2(exe_path, backup_path)


        status.update("[bold green]Downloading new binary...[/bold green]")
        try:
            status.stop()
            sha256 = hashlib.sha256()
            with requests.get(exe_url, stream=True) as r:
                r.raise_for_status()
                total = int(r.headers.get('Content-Length', 0))
                with open(tmp_path, 'wb') as f, Progress(
                    SpinnerColumn(),
                    TextColumn("{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TimeRemainingColumn(),
                    transient=True,
                ) as progress:
                    task = progress.add_task("[cyan]Downloading...", total=total)
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            sha256.update(chunk)
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))

            if checksum:
                if f"sha256:{sha256.hexdigest()}" != checksum:
                    console.print("[bold red]❌ Checksum mismatch. Aborting update.[/bold red]")
                    os.remove(tmp_path)
                    raise typer.Exit(code=1)
            else:
                console.print("[bold yellow]⚠ No checksum provided. Skipping verification.[/bold yellow]")

            os.replace(tmp_path, exe_path)

            status.start()

        except Exception as e:
            console.print(f"[bold red]❌ Failed to download or verify: {e}[/bold red]")
            if os.path.exists(exe_path + ".bak"):
                shutil.move(exe_path + ".bak", exe_path)
                console.print("[yellow]🔁 Restored previous version from backup.[/yellow]")
            raise typer.Exit(code=1)

        status.update("[bold green]Finalizing PATH...[/bold green]")
        add_folder_to_path(CMAM_SCRIPTS)

        status.update("[bold green]Saving metadata...[/bold green]")
        data[app_name] = {"version": new_version}
        save_local_packages(data)

    if os.path.exists(exe_path + ".bak") and not keep_backup:
        os.remove(exe_path + ".bak")


    console.print(Panel(
        f"[bold green]✅ {app_name} v{new_version} updated successfully![/bold green]\n\n"
        "You can now run your updated app from any terminal window.",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))
    if not already_in_path:
        console.print("[yellow]💡 Tip: Restart your terminal to apply PATH changes.[/yellow]")

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  PLACEHOLDER/NOT IMPLEMENTED COMMANDS                                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.command()
def uninstall():
    """Uninstalls a currently installed app."""
    not_implemented_message("uninstall")

@app.command()
def list():
    """Lists all installed apps with their versions."""
    not_implemented_message("list")

@app.command()
def info():
    """Shows detailed info about a specified app."""
    not_implemented_message("info")

@app.command()
def search():
    """Searches for apps available in the remote repository."""
    not_implemented_message("search")

@app.command()
def self_update():
    """Updates CMAM."""
    not_implemented_message("self-update")

@app.command()
def repair():
    """Repairs a corrupted app by uninstalling and reinstalling it."""
    not_implemented_message("repair")

@app.command()
def validate():
    """Checks if all installed apps match their expected checksums."""
    not_implemented_message("validate")

@app.command()
def clean():
    """Cleans up cache files, temp data, and optionally orphaned apps."""
    not_implemented_message("clean")

@app.command()
def doctor():
    """Runs a health diagnostic on environment and configuration."""
    not_implemented_message("doctor")

@app.command()
def verify():
    """Verifies the checksum of a specified installed app."""
    not_implemented_message("verify")

@app.command()
def trust():
    """Displays the verification status of installed app signatures."""
    not_implemented_message("trust")

@app.command()
def path():
    """Checks or re-adds the install directory to your PATH."""
    not_implemented_message("path")

@app.command()
def export():
    """Exports the list of installed apps to a manifest file."""
    not_implemented_message("export")

@app.command()
def import_():
    """Installs all apps listed in a provided manifest file."""
    not_implemented_message("import")

@app.command()
def rollback():
    """Rolls back an app to a previous installed version."""
    not_implemented_message("rollback")

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  ENTRY POINT & ERROR HANDLING                                              ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def main():
    try:
        app()
    except Exception as e:
        console.print(f"[bold red]❌ Unhandled error: {e}[/bold red]")
        raise

if __name__ == "__main__":
    main()
