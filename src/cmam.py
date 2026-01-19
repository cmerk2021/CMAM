# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  CMAM - Connor Merk App Manager                                            ║
# ║  Package manager for installing and managing Connor Merk's applications.   ║
# ║  Copyright (c) 2026 Connor Merk                                            ║
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
from rich.prompt import Confirm
from typing import Optional, List

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  CONSTANTS & GLOBALS                                                       ║
# ╚════════════════════════════════════════════════════════════════════════════╝

CMAM_VERSION = "2.1.0"
CMAM_ROOT = r"C:\.cmam"
CMAM_CACHE = os.path.join(CMAM_ROOT, ".cache")
CMAM_SCRIPTS = os.path.join(CMAM_ROOT, "scripts")
CMAM_BACKUPS = os.path.join(CMAM_CACHE, "backups")
CMAM_PACKAGES_JSON = os.path.join(CMAM_ROOT, "packages.json")
CMAM_PACKAGES_TXT = os.path.join(CMAM_ROOT, "packages.txt")
GITHUB_MANIFEST_URL = "https://api.github.com/repos/cmerk2021/cmam/contents/packages.json"
CMAM_REPO = "cmerk2021/cmam"

console = Console()

def version_callback(value: bool):
    """Callback for --version flag."""
    if value:
        console.print(f"[bold blue]CMAM[/bold blue] version [green]{CMAM_VERSION}[/green]")
        raise typer.Exit()

app = typer.Typer(
    help="CMAM: Connor Merk App Manager - Your package manager for Connor Merk's apps.",
    no_args_is_help=True
)

@app.callback()
def main_callback(
    version: bool = typer.Option(None, "--version", "-V", callback=version_callback, is_eager=True, help="Show version and exit.")
):
    """CMAM: Connor Merk App Manager"""
    check_cmam_update()

already_in_path = False

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  UTILITY FUNCTIONS                                                         ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def check_cmam_update():
    """Check if a newer version of CMAM is available and warn the user."""
    try:
        api_url = f"https://api.github.com/repos/{CMAM_REPO}/releases/latest"
        response = requests.get(api_url, timeout=3)
        response.raise_for_status()
        release_data = response.json()
        latest_version = release_data.get("tag_name", "").lstrip("v")
        
        if latest_version and parse_version(latest_version) > parse_version(CMAM_VERSION):
            console.print(
                f"[bold yellow]⚠ A new version of CMAM is available: v{latest_version} (current: v{CMAM_VERSION})[/bold yellow]\n"
                f"[dim]Run 'cmam self-update' to update.[/dim]\n"
            )
    except Exception:
        # Silently ignore any errors - don't interrupt the user's command
        pass

def parse_version(v: str):
    """Parse a version string into a comparable tuple, handling pre-releases."""
    import re

    v = v.strip("v")
    match = re.match(r"(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9]+))?", v)
    if not match:
        raise ValueError(f"Invalid version format: {v}")

    major, minor, patch, pre = match.groups()
    version_tuple = (int(major), int(minor), int(patch))

    pre_map = {
        None: 3,
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
            f"[bold blue]CMAM[/bold blue] [white]v{CMAM_VERSION}[/white]\n"
            "[green]Connor Merk App Manager[/green]\n"
            "[dim]https://github.com/cmerk2021/cmam[/dim]",
            border_style="blue",
            expand=False
        )
    )

def ensure_dirs():
    """Ensure all required directories exist."""
    for folder in [CMAM_ROOT, CMAM_CACHE, CMAM_SCRIPTS, CMAM_BACKUPS]:
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

def fetch_release_info(repo: str, version: str = None):
    """Fetch release information from a GitHub repo."""
    if version:
        api_url = f"https://api.github.com/repos/{repo}/releases/tags/v{version}"
    else:
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except HTTPError as e:
        if response.status_code == 404:
            return None
        raise
    except requests.RequestException:
        return None

def get_exe_asset(release_data: dict):
    """Extract exe asset info from release data."""
    for asset in release_data.get('assets', []):
        if asset.get('name', '').lower().endswith('.exe'):
            return {
                'url': asset.get('browser_download_url'),
                'checksum': asset.get('digest'),
                'filename': asset['name']
            }
    return None

def calculate_file_checksum(filepath: str) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"

def download_file_with_progress(url: str, dest_path: str) -> str:
    """Download a file with progress bar, returns checksum."""
    sha256 = hashlib.sha256()
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get('Content-Length', 0))
        with open(dest_path, 'wb') as f, Progress(
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
    return f"sha256:{sha256.hexdigest()}"

def create_backup(app_name: str, version: str):
    """Create a versioned backup of an app."""
    exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
    if os.path.exists(exe_path):
        ensure_dirs()
        backup_path = os.path.join(CMAM_BACKUPS, f"{app_name}_v{version}.exe.bak")
        shutil.copy2(exe_path, backup_path)
        return backup_path
    return None

def get_backups(app_name: str) -> List[dict]:
    """Get list of backups for an app, sorted by version (newest first)."""
    backups = []
    if os.path.exists(CMAM_BACKUPS):
        for filename in os.listdir(CMAM_BACKUPS):
            if filename.startswith(f"{app_name}_v") and filename.endswith(".exe.bak"):
                version = filename.replace(f"{app_name}_v", "").replace(".exe.bak", "")
                filepath = os.path.join(CMAM_BACKUPS, filename)
                backups.append({
                    'version': version,
                    'path': filepath,
                    'filename': filename
                })
    backups.sort(key=lambda x: parse_version(x['version']), reverse=True)
    return backups

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

def is_in_path(folder_path: str) -> bool:
    """Check if a folder is in the user's PATH."""
    folder_path = os.path.abspath(folder_path)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ)
        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""
        winreg.CloseKey(key)
        
        paths = [os.path.normpath(p).lower() for p in current_path.split(';') if p.strip()]
        return folder_path.lower() in paths
    except Exception:
        return False

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

        status.update("[bold green]Fetching application manifest...[/bold green]")
        app_manifest = fetch_manifest()
        if app_name not in app_manifest:
            console.print(f"[bold red]❌ App [blue]{app_name}[/blue] not found in manifest.[/bold red]")
            raise typer.Exit(code=1)
        app_data = app_manifest[app_name]

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

        status.start()
        status.update("[bold green]Finalizing PATH...[/bold green]")
        add_folder_to_path(CMAM_SCRIPTS)

        status.update("[bold green]Saving metadata...[/bold green]")
        data = load_local_packages()
        data[app_name] = {"version": app_version.replace("v", "")}
        save_local_packages(data)

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
    keep_backup: bool = typer.Option(True, "--keep-backup", "-k", help="Keep backup of the old binary."),
):
    """Updates an application from the CMAM repository."""

    print_banner()
    console.print(f"[bold cyan]🔧 Updating [green]{app_name}[/green]"
                  + (f" [magenta](v{version})[/magenta]" if version else "") + "...[/bold cyan]")

    exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
    if not os.path.exists(exe_path):
        console.print(f"[bold red]⚠ App [blue]{app_name}[/blue] is not installed. Use [bold blue]install[/bold blue] instead.[/bold red]")
        raise typer.Exit(code=1)

    with console.status("[bold green]Preparing update...[/bold green]") as status:
        status.update("[bold green]Fetching application manifest...[/bold green]")
        app_manifest = fetch_manifest()
        if app_name not in app_manifest:
            console.print(f"[bold red]❌ App [blue]{app_name}[/blue] not found in manifest.[/bold red]")
            raise typer.Exit(code=1)
        app_data = app_manifest[app_name]

        data = load_local_packages()
        current_version = data.get(app_name, {}).get("version", "unknown")

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
            console.print(f"[bold yellow]⚠ App [blue]{app_name}[/blue] is already at version [magenta]{new_version}[/magenta]. No update needed.[/bold yellow]")
            raise typer.Exit(code=0)

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
        if keep_backup:
            create_backup(app_name, current_version)

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
            raise typer.Exit(code=1)

        status.update("[bold green]Finalizing PATH...[/bold green]")
        add_folder_to_path(CMAM_SCRIPTS)

        status.update("[bold green]Saving metadata...[/bold green]")
        data[app_name] = {"version": new_version}
        save_local_packages(data)

    console.print(Panel(
        f"[bold green]✅ {app_name} updated from v{current_version} to v{new_version}![/bold green]\n\n"
        "You can now run your updated app from any terminal window.",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))
    if not already_in_path:
        console.print("[yellow]💡 Tip: Restart your terminal to apply PATH changes.[/yellow]")

@app.command("update-all")
def update_all(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    keep_backup: bool = typer.Option(True, "--keep-backup", "-k", help="Keep backups of old binaries."),
):
    """Checks and updates all installed apps to their latest versions."""
    print_banner()
    console.print("[bold cyan]🔄 Checking for updates for all installed apps...[/bold cyan]\n")
    
    data = load_local_packages()
    
    if not data:
        console.print("[yellow]📭 No apps installed.[/yellow]")
        return
    
    # Check for updates
    updates_available = []
    
    with console.status("[bold green]Fetching manifest and checking versions...[/bold green]"):
        manifest = fetch_manifest()
        
        for app_name, info in data.items():
            current_version = info.get("version", "unknown")
            
            if app_name not in manifest:
                continue
            
            app_link = manifest[app_name]["link"]
            release_info = fetch_release_info(app_link)
            
            if not release_info:
                continue
            
            latest_version = release_info.get("tag_name", "").lstrip("v")
            
            if current_version != latest_version and latest_version:
                try:
                    if parse_version(latest_version) > parse_version(current_version):
                        updates_available.append({
                            'name': app_name,
                            'current': current_version,
                            'latest': latest_version
                        })
                except Exception:
                    # Skip apps with invalid version formats
                    pass
    
    if not updates_available:
        console.print("[bold green]✅ All apps are up to date![/bold green]")
        return
    
    # Show what will be updated
    table = Table(title="[bold blue]Updates Available[/bold blue]")
    table.add_column("App", style="cyan")
    table.add_column("Current", style="yellow")
    table.add_column("Latest", style="green")
    
    for update in updates_available:
        table.add_row(
            update['name'],
            f"v{update['current']}",
            f"v{update['latest']}"
        )
    
    console.print(table)
    console.print(f"\n[bold]{len(updates_available)} update(s) available[/bold]")
    
    # Confirm
    if not yes and not Confirm.ask("\n[bold cyan]Proceed with updates?[/bold cyan]"):
        console.print("[yellow]Update cancelled.[/yellow]")
        return
    
    # Perform updates
    console.print("\n[bold cyan]Starting updates...[/bold cyan]\n")
    
    success_count = 0
    fail_count = 0
    failed_apps = []
    
    for update_info in updates_available:
        app_name = update_info['name']
        console.print(f"[bold]Updating {app_name}...[/bold]")
        
        try:
            # Perform the update using existing update logic
            exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
            current_version = update_info['current']
            new_version = update_info['latest']
            
            with console.status(f"[bold green]Updating {app_name}...[/bold green]") as status:
                app_link = manifest[app_name]["link"]
                api_url = f"https://api.github.com/repos/{app_link}/releases/latest"
                
                response = requests.get(api_url)
                response.raise_for_status()
                release_data = response.json()
                
                exe_url, checksum = None, None
                for asset in release_data.get('assets', []):
                    if asset.get('name', '').lower().endswith('.exe'):
                        exe_url = asset.get('browser_download_url')
                        checksum = asset.get("digest")
                        break
                
                if not exe_url:
                    raise Exception("No .exe asset found")
                
                if keep_backup:
                    status.update("[bold green]Backing up...[/bold green]")
                    create_backup(app_name, current_version)
                
                tmp_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe.tmp")
                
                status.stop()
                sha256 = hashlib.sha256()
                with requests.get(exe_url, stream=True) as r:
                    r.raise_for_status()
                    total = int(r.headers.get('Content-Length', 0))
                    with open(tmp_path, 'wb') as f, Progress(
                        SpinnerColumn(),
                        TextColumn(f"{{task.description}} [dim]{app_name}[/dim]"),
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
                
                if checksum and f"sha256:{sha256.hexdigest()}" != checksum:
                    os.remove(tmp_path)
                    raise Exception("Checksum mismatch")
                
                os.replace(tmp_path, exe_path)
                status.start()
                
                status.update("[bold green]Saving metadata...[/bold green]")
                data = load_local_packages()
                data[app_name]["version"] = new_version
                save_local_packages(data)
            
            console.print(f"  [green]✓[/green] {app_name} updated to v{new_version}\n")
            success_count += 1
            
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed to update {app_name}: {e}\n")
            fail_count += 1
            failed_apps.append(app_name)
    
    # Summary
    console.print(Panel(
        f"[bold green]Update complete![/bold green]\n\n"
        f"✅ Successfully updated: {success_count}\n"
        f"❌ Failed: {fail_count}" +
        (f"\n\n[red]Failed apps:[/red] {', '.join(failed_apps)}" if failed_apps else ""),
        title="[bold blue]CMAM[/bold blue]",
        border_style="green" if fail_count == 0 else "yellow"
    ))
    
    if success_count > 0 and not already_in_path:
        console.print("[yellow]💡 Tip: Restart your terminal if PATH changes were made.[/yellow]")

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  IMPLEMENTED COMMANDS                                                      ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.command()
def uninstall(
    app_name: str = typer.Argument(..., help="Name of the application to uninstall."),
    keep_backups: bool = typer.Option(False, "--keep-backups", "-k", help="Keep backup files for this app.")
):
    """Uninstalls a currently installed app."""
    print_banner()
    console.print(f"[bold cyan]🗑️  Uninstalling [green]{app_name}[/green]...[/bold cyan]")
    
    exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
    
    if not os.path.exists(exe_path):
        console.print(f"[bold red]❌ App [blue]{app_name}[/blue] is not installed.[/bold red]")
        raise typer.Exit(code=1)
    
    with console.status("[bold green]Removing application...[/bold green]") as status:
        # Remove the executable
        try:
            os.remove(exe_path)
        except Exception as e:
            console.print(f"[bold red]❌ Failed to remove executable: {e}[/bold red]")
            raise typer.Exit(code=1)
        
        # Remove backups if not keeping them
        if not keep_backups:
            status.update("[bold green]Removing backups...[/bold green]")
            backups = get_backups(app_name)
            for backup in backups:
                try:
                    os.remove(backup['path'])
                except Exception:
                    pass
        
        # Update packages.json
        status.update("[bold green]Updating package registry...[/bold green]")
        data = load_local_packages()
        if app_name in data:
            del data[app_name]
            save_local_packages(data)
    
    console.print(Panel(
        f"[bold green]✅ {app_name} uninstalled successfully![/bold green]",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))

@app.command("list")
def list_apps():
    """Lists all installed apps with their versions."""
    print_banner()
    
    data = load_local_packages()
    
    if not data:
        console.print("[yellow]📭 No apps installed yet. Use [bold blue]cmam install <app>[/bold blue] to get started.[/yellow]")
        return
    
    table = Table(title="[bold blue]Installed Applications[/bold blue]")
    table.add_column("App Name", style="cyan", no_wrap=True)
    table.add_column("Version", style="green")
    table.add_column("Backups", style="yellow")
    
    for app_name, info in sorted(data.items()):
        version = info.get("version", "unknown")
        backups = get_backups(app_name)
        backup_count = str(len(backups)) if backups else "0"
        table.add_row(app_name, f"v{version}", backup_count)
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(data)} app(s) installed[/dim]")

@app.command()
def info(
    app_name: str = typer.Argument(..., help="Name of the application to get info about.")
):
    """Shows detailed info about a specified app."""
    print_banner()
    
    with console.status("[bold green]Fetching app information...[/bold green]"):
        manifest = fetch_manifest()
        local_packages = load_local_packages()
    
    if app_name not in manifest:
        console.print(f"[bold red]❌ App [blue]{app_name}[/blue] not found in manifest.[/bold red]")
        raise typer.Exit(code=1)
    
    app_data = manifest[app_name]
    is_installed = app_name in local_packages
    installed_version = local_packages.get(app_name, {}).get("version") if is_installed else None
    
    # Fetch latest release info
    release_info = fetch_release_info(app_data["link"])
    latest_version = release_info.get("tag_name", "").lstrip("v") if release_info else "unknown"
    
    # Build info panel
    info_lines = [
        f"[bold]Name:[/bold] {app_name}",
        f"[bold]Repository:[/bold] github.com/{app_data['link']}",
    ]
    
    if "description" in app_data:
        info_lines.append(f"[bold]Description:[/bold] {app_data['description']}")
    
    info_lines.append(f"[bold]Latest Version:[/bold] v{latest_version}")
    
    if is_installed:
        info_lines.append(f"[bold]Installed Version:[/bold] [green]v{installed_version}[/green]")
        if installed_version != latest_version:
            info_lines.append("[yellow]⚠ Update available![/yellow]")
        
        # Show backups
        backups = get_backups(app_name)
        if backups:
            backup_versions = ", ".join([f"v{b['version']}" for b in backups[:5]])
            if len(backups) > 5:
                backup_versions += f" (+{len(backups) - 5} more)"
            info_lines.append(f"[bold]Backups:[/bold] {backup_versions}")
    else:
        info_lines.append("[dim]Status: Not installed[/dim]")
    
    console.print(Panel(
        "\n".join(info_lines),
        title=f"[bold blue]📦 {app_name}[/bold blue]",
        border_style="blue"
    ))

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (searches app names).")
):
    """Searches for apps available in the remote repository."""
    print_banner()
    
    with console.status("[bold green]Searching...[/bold green]"):
        manifest = fetch_manifest()
        local_packages = load_local_packages()
    
    # Search by name (case-insensitive)
    query_lower = query.lower()
    matches = {name: data for name, data in manifest.items() if query_lower in name.lower()}
    
    if not matches:
        console.print(f"[yellow]🔍 No apps found matching '{query}'[/yellow]")
        return
    
    table = Table(title=f"[bold blue]Search Results for '{query}'[/bold blue]")
    table.add_column("App Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Status", style="green")
    
    for name, data in sorted(matches.items()):
        description = data.get("description", "[dim]No description[/dim]")
        if name in local_packages:
            status = f"[green]✓ v{local_packages[name].get('version', '?')}[/green]"
        else:
            status = "[dim]Not installed[/dim]"
        table.add_row(name, description, status)
    
    console.print(table)
    console.print(f"\n[dim]Found {len(matches)} app(s)[/dim]")

@app.command()
def self_update():
    """Updates CMAM itself to the latest version."""
    print_banner()
    console.print("[bold cyan]🔄 Checking for CMAM updates...[/bold cyan]")
    
    with console.status("[bold green]Fetching latest CMAM release...[/bold green]") as status:
        release_info = fetch_release_info(CMAM_REPO)
        
        if not release_info:
            console.print("[bold red]❌ Failed to fetch CMAM release information.[/bold red]")
            raise typer.Exit(code=1)
        
        latest_version = release_info.get("tag_name", "").lstrip("v")
        
        if parse_version(CMAM_VERSION) >= parse_version(latest_version):
            console.print(f"[bold green]✅ CMAM is already up to date (v{CMAM_VERSION})[/bold green]")
            return
        
        console.print(f"[bold yellow]📦 New version available: v{latest_version} (current: v{CMAM_VERSION})[/bold yellow]")
        
        # Find exe asset
        asset = get_exe_asset(release_info)
        if not asset:
            console.print("[bold red]❌ No CMAM executable found in release.[/bold red]")
            raise typer.Exit(code=1)
        
        # Determine current exe path
        current_exe = os.path.join(CMAM_SCRIPTS, "cmam.exe")
        if not os.path.exists(current_exe):
            current_exe = sys.executable if getattr(sys, 'frozen', False) else None
        
        if not current_exe or not os.path.exists(current_exe):
            console.print("[bold red]❌ Cannot locate current CMAM executable.[/bold red]")
            raise typer.Exit(code=1)
        
        # Backup current version
        status.update("[bold green]Backing up current version...[/bold green]")
        create_backup("cmam", CMAM_VERSION)
        
        # Download new version
        status.update("[bold green]Downloading new version...[/bold green]")
        tmp_path = current_exe + ".tmp"
        
        status.stop()
        try:
            checksum = download_file_with_progress(asset['url'], tmp_path)
            
            if asset['checksum'] and checksum != asset['checksum']:
                console.print("[bold red]❌ Checksum mismatch. Aborting update.[/bold red]")
                os.remove(tmp_path)
                raise typer.Exit(code=1)
            
            # Create a batch script to replace the exe after this process exits
            batch_path = os.path.join(CMAM_CACHE, "update_cmam.bat")
            with open(batch_path, 'w') as f:
                f.write(f'''@echo off
timeout /t 2 /nobreak >nul
move /y "{tmp_path}" "{current_exe}"
echo CMAM updated successfully!
del "%~f0"
''')
            
            console.print(Panel(
                f"[bold green]✅ CMAM v{latest_version} downloaded![/bold green]\n\n"
                "[yellow]The update will be applied when you restart CMAM.[/yellow]",
                title="[bold blue]CMAM[/bold blue]",
                border_style="green"
            ))
            
            # Run the batch script
            os.startfile(batch_path)
            
        except Exception as e:
            console.print(f"[bold red]❌ Failed to download update: {e}[/bold red]")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise typer.Exit(code=1)

@app.command()
def repair(
    app_name: str = typer.Argument(..., help="Name of the application to repair.")
):
    """Repairs a corrupted app by reinstalling it."""
    print_banner()
    console.print(f"[bold cyan]🔧 Repairing [green]{app_name}[/green]...[/bold cyan]")
    
    data = load_local_packages()
    
    if app_name not in data:
        console.print(f"[bold red]❌ App [blue]{app_name}[/blue] is not installed.[/bold red]")
        raise typer.Exit(code=1)
    
    current_version = data[app_name].get("version", "unknown")
    exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
    
    # Remove the current exe if it exists
    if os.path.exists(exe_path):
        try:
            os.remove(exe_path)
        except Exception as e:
            console.print(f"[bold red]❌ Failed to remove existing file: {e}[/bold red]")
            raise typer.Exit(code=1)
    
    # Remove from packages.json temporarily
    del data[app_name]
    save_local_packages(data)
    
    # Reinstall the same version
    console.print(f"[dim]Reinstalling v{current_version}...[/dim]")
    
    # Call install with the specific version
    try:
        install(app_name, version=current_version)
    except SystemExit:
        # If install fails, it will print its own error
        raise

@app.command()
def rollback(
    app_name: str = typer.Argument(..., help="Name of the application to roll back."),
    version: str = typer.Option(None, "--version", "-v", help="Specific version to roll back to.")
):
    """Rolls back an app to a previous installed version."""
    print_banner()
    
    data = load_local_packages()
    
    if app_name not in data:
        console.print(f"[bold red]❌ App [blue]{app_name}[/blue] is not installed.[/bold red]")
        raise typer.Exit(code=1)
    
    backups = get_backups(app_name)
    
    if not backups:
        console.print(f"[bold red]❌ No backups found for [blue]{app_name}[/blue].[/bold red]")
        raise typer.Exit(code=1)
    
    # Show available backups
    if not version:
        console.print("[bold cyan]📦 Available backups:[/bold cyan]")
        table = Table()
        table.add_column("Version", style="green")
        table.add_column("Path", style="dim")
        for backup in backups:
            table.add_row(f"v{backup['version']}", backup['path'])
        console.print(table)
        console.print("\n[yellow]Use --version to specify which version to roll back to.[/yellow]")
        return
    
    # Find the requested backup
    target_backup = None
    for backup in backups:
        if backup['version'] == version:
            target_backup = backup
            break
    
    if not target_backup:
        console.print(f"[bold red]❌ No backup found for version v{version}.[/bold red]")
        raise typer.Exit(code=1)
    
    current_version = data[app_name].get("version", "unknown")
    exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
    
    with console.status("[bold green]Rolling back...[/bold green]") as status:
        # Backup current version first
        status.update("[bold green]Backing up current version...[/bold green]")
        create_backup(app_name, current_version)
        
        # Restore from backup
        status.update("[bold green]Restoring from backup...[/bold green]")
        try:
            shutil.copy2(target_backup['path'], exe_path)
        except Exception as e:
            console.print(f"[bold red]❌ Failed to restore backup: {e}[/bold red]")
            raise typer.Exit(code=1)
        
        # Update packages.json
        status.update("[bold green]Updating package registry...[/bold green]")
        data[app_name]["version"] = version
        save_local_packages(data)
    
    console.print(Panel(
        f"[bold green]✅ {app_name} rolled back from v{current_version} to v{version}![/bold green]",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))

@app.command("export")
def export_apps(
    output: str = typer.Option("cmam-export.json", "--output", "-o", help="Output file path.")
):
    """Exports the list of installed apps to a manifest file."""
    print_banner()
    
    data = load_local_packages()
    
    if not data:
        console.print("[yellow]📭 No apps installed to export.[/yellow]")
        return
    
    export_data = {
        "cmam_version": CMAM_VERSION,
        "apps": {}
    }
    
    for app_name, info in data.items():
        export_data["apps"][app_name] = {
            "version": info.get("version", "latest")
        }
    
    try:
        with open(output, 'w') as f:
            json.dump(export_data, f, indent=2)
        console.print(Panel(
            f"[bold green]✅ Exported {len(data)} app(s) to [cyan]{output}[/cyan][/bold green]",
            title="[bold blue]CMAM[/bold blue]",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[bold red]❌ Failed to export: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command("import")
def import_apps(
    input_file: str = typer.Argument(..., help="Path to the manifest file to import."),
    skip_existing: bool = typer.Option(True, "--skip-existing", "-s", help="Skip apps that are already installed.")
):
    """Installs all apps listed in a provided manifest file."""
    print_banner()
    
    if not os.path.exists(input_file):
        console.print(f"[bold red]❌ File not found: {input_file}[/bold red]")
        raise typer.Exit(code=1)
    
    try:
        with open(input_file, 'r') as f:
            import_data = json.load(f)
    except json.JSONDecodeError:
        console.print("[bold red]❌ Invalid JSON file.[/bold red]")
        raise typer.Exit(code=1)
    
    apps = import_data.get("apps", {})
    
    if not apps:
        console.print("[yellow]📭 No apps found in manifest.[/yellow]")
        return
    
    local_packages = load_local_packages()
    
    console.print(f"[bold cyan]📦 Importing {len(apps)} app(s)...[/bold cyan]\n")
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for app_name, info in apps.items():
        version = info.get("version")
        
        if skip_existing and app_name in local_packages:
            console.print(f"[yellow]⏭️  Skipping {app_name} (already installed)[/yellow]")
            skip_count += 1
            continue
        
        try:
            console.print(f"\n[bold]Installing {app_name}...[/bold]")
            # Remove existing entry if we're reinstalling
            if app_name in local_packages:
                exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
                if os.path.exists(exe_path):
                    os.remove(exe_path)
                del local_packages[app_name]
                save_local_packages(local_packages)
            
            install(app_name, version=version)
            success_count += 1
            local_packages = load_local_packages()  # Reload after install
        except SystemExit:
            fail_count += 1
            continue
    
    console.print(Panel(
        f"[bold green]Import complete![/bold green]\n\n"
        f"✅ Installed: {success_count}\n"
        f"⏭️  Skipped: {skip_count}\n"
        f"❌ Failed: {fail_count}",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))

@app.command()
def validate():
    """Checks if all installed apps match their expected checksums."""
    print_banner()
    console.print("[bold cyan]🔍 Validating all installed apps...[/bold cyan]\n")
    
    data = load_local_packages()
    
    if not data:
        console.print("[yellow]📭 No apps installed to validate.[/yellow]")
        return
    
    with console.status("[bold green]Fetching manifest...[/bold green]"):
        manifest = fetch_manifest()
    
    table = Table(title="[bold blue]Validation Results[/bold blue]")
    table.add_column("App", style="cyan")
    table.add_column("Version", style="white")
    table.add_column("Status", style="white")
    
    valid_count = 0
    invalid_count = 0
    unknown_count = 0
    
    for app_name, info in data.items():
        version = info.get("version", "unknown")
        exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
        
        if not os.path.exists(exe_path):
            table.add_row(app_name, f"v{version}", "[red]❌ Missing[/red]")
            invalid_count += 1
            continue
        
        if app_name not in manifest:
            table.add_row(app_name, f"v{version}", "[yellow]⚠ Not in manifest[/yellow]")
            unknown_count += 1
            continue
        
        # Fetch release to get expected checksum
        release_info = fetch_release_info(manifest[app_name]["link"], version)
        if not release_info:
            table.add_row(app_name, f"v{version}", "[yellow]⚠ Cannot fetch release[/yellow]")
            unknown_count += 1
            continue
        
        asset = get_exe_asset(release_info)
        if not asset or not asset.get('checksum'):
            table.add_row(app_name, f"v{version}", "[yellow]⚠ No checksum available[/yellow]")
            unknown_count += 1
            continue
        
        # Calculate local checksum
        local_checksum = calculate_file_checksum(exe_path)
        
        if local_checksum == asset['checksum']:
            table.add_row(app_name, f"v{version}", "[green]✅ Valid[/green]")
            valid_count += 1
        else:
            table.add_row(app_name, f"v{version}", "[red]❌ Checksum mismatch[/red]")
            invalid_count += 1
    
    console.print(table)
    console.print(f"\n[green]✅ Valid: {valid_count}[/green] | [red]❌ Invalid: {invalid_count}[/red] | [yellow]⚠ Unknown: {unknown_count}[/yellow]")

@app.command()
def verify(
    app_name: str = typer.Argument(..., help="Name of the application to verify.")
):
    """Verifies the checksum of a specified installed app."""
    print_banner()
    
    data = load_local_packages()
    
    if app_name not in data:
        console.print(f"[bold red]❌ App [blue]{app_name}[/blue] is not installed.[/bold red]")
        raise typer.Exit(code=1)
    
    exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
    
    if not os.path.exists(exe_path):
        console.print(f"[bold red]❌ Executable not found for [blue]{app_name}[/blue].[/bold red]")
        raise typer.Exit(code=1)
    
    version = data[app_name].get("version", "unknown")
    
    with console.status("[bold green]Verifying checksum...[/bold green]"):
        manifest = fetch_manifest()
        
        if app_name not in manifest:
            console.print(f"[bold yellow]⚠ App [blue]{app_name}[/blue] not found in manifest. Cannot verify.[/bold yellow]")
            raise typer.Exit(code=1)
        
        release_info = fetch_release_info(manifest[app_name]["link"], version)
        
        if not release_info:
            console.print(f"[bold yellow]⚠ Cannot fetch release info for v{version}.[/bold yellow]")
            raise typer.Exit(code=1)
        
        asset = get_exe_asset(release_info)
        local_checksum = calculate_file_checksum(exe_path)
    
    console.print(f"[bold]Local checksum:[/bold] {local_checksum}")
    
    if asset and asset.get('checksum'):
        console.print(f"[bold]Expected checksum:[/bold] {asset['checksum']}")
        
        if local_checksum == asset['checksum']:
            console.print(Panel(
                f"[bold green]✅ {app_name} v{version} is verified and authentic![/bold green]",
                title="[bold blue]CMAM[/bold blue]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[bold red]❌ {app_name} v{version} failed verification![/bold red]\n"
                "[yellow]The file may be corrupted or tampered with. Consider running 'cmam repair'.[/yellow]",
                title="[bold blue]CMAM[/bold blue]",
                border_style="red"
            ))
            raise typer.Exit(code=1)
    else:
        console.print("[yellow]⚠ No remote checksum available for comparison.[/yellow]")

@app.command()
def clean(
    cache: bool = typer.Option(True, "--cache/--no-cache", help="Clean cache files."),
    orphans: bool = typer.Option(True, "--orphans/--no-orphans", help="Remove orphaned apps."),
    backups: bool = typer.Option(False, "--backups", "-b", help="Also remove all backups (use with caution).")
):
    """Cleans up cache files, temp data, and optionally orphaned apps."""
    print_banner()
    console.print("[bold cyan]🧹 Cleaning up...[/bold cyan]\n")
    
    cleaned_size = 0
    cleaned_files = 0
    
    # Clean cache (excluding backups unless specified)
    if cache:
        console.print("[bold]Cleaning cache...[/bold]")
        if os.path.exists(CMAM_CACHE):
            for item in os.listdir(CMAM_CACHE):
                item_path = os.path.join(CMAM_CACHE, item)
                
                # Skip backups folder unless --backups is specified
                if item == "backups" and not backups:
                    continue
                
                try:
                    if os.path.isfile(item_path):
                        cleaned_size += os.path.getsize(item_path)
                        os.remove(item_path)
                        cleaned_files += 1
                    elif os.path.isdir(item_path):
                        for root, dirs, files in os.walk(item_path):
                            for f in files:
                                fp = os.path.join(root, f)
                                cleaned_size += os.path.getsize(fp)
                                cleaned_files += 1
                        shutil.rmtree(item_path)
                except Exception as e:
                    console.print(f"[yellow]⚠ Could not remove {item}: {e}[/yellow]")
        console.print(f"  [green]✓[/green] Cache cleaned")
    
    # Clean backups with warning
    if backups:
        if not Confirm.ask("[bold red]⚠ Are you sure you want to delete ALL backups? This cannot be undone.[/bold red]"):
            console.print("[yellow]Skipping backup deletion.[/yellow]")
        else:
            if os.path.exists(CMAM_BACKUPS):
                for item in os.listdir(CMAM_BACKUPS):
                    item_path = os.path.join(CMAM_BACKUPS, item)
                    try:
                        cleaned_size += os.path.getsize(item_path)
                        os.remove(item_path)
                        cleaned_files += 1
                    except Exception:
                        pass
                console.print(f"  [green]✓[/green] Backups cleaned")
    
    # Clean orphaned apps
    if orphans:
        console.print("[bold]Checking for orphaned apps...[/bold]")
        data = load_local_packages()
        
        if os.path.exists(CMAM_SCRIPTS):
            for filename in os.listdir(CMAM_SCRIPTS):
                if filename.endswith('.exe'):
                    app_name = filename[:-4]  # Remove .exe
                    if app_name not in data and app_name != "cmam":
                        exe_path = os.path.join(CMAM_SCRIPTS, filename)
                        try:
                            cleaned_size += os.path.getsize(exe_path)
                            os.remove(exe_path)
                            cleaned_files += 1
                            console.print(f"  [green]✓[/green] Removed orphaned app: {app_name}")
                        except Exception as e:
                            console.print(f"  [yellow]⚠[/yellow] Could not remove {app_name}: {e}")
    
    # Format size
    if cleaned_size < 1024:
        size_str = f"{cleaned_size} B"
    elif cleaned_size < 1024 * 1024:
        size_str = f"{cleaned_size / 1024:.1f} KB"
    else:
        size_str = f"{cleaned_size / (1024 * 1024):.1f} MB"
    
    console.print(Panel(
        f"[bold green]✅ Cleanup complete![/bold green]\n\n"
        f"Files removed: {cleaned_files}\n"
        f"Space freed: {size_str}",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))

@app.command()
def doctor():
    """Runs a health diagnostic on environment and configuration."""
    print_banner()
    console.print("[bold cyan]🩺 Running diagnostics...[/bold cyan]\n")
    
    issues = []
    warnings = []
    
    # Check 1: CMAM directories exist
    console.print("[bold]Checking directories...[/bold]")
    for name, path in [("Root", CMAM_ROOT), ("Cache", CMAM_CACHE), ("Scripts", CMAM_SCRIPTS), ("Backups", CMAM_BACKUPS)]:
        if os.path.exists(path):
            console.print(f"  [green]✓[/green] {name} directory exists: {path}")
        else:
            console.print(f"  [yellow]⚠[/yellow] {name} directory missing: {path}")
            warnings.append(f"{name} directory missing")
    
    # Check 2: packages.json is valid
    console.print("\n[bold]Checking package registry...[/bold]")
    try:
        data = load_local_packages()
        console.print(f"  [green]✓[/green] packages.json is valid ({len(data)} apps registered)")
    except Exception as e:
        console.print(f"  [red]✗[/red] packages.json is corrupted: {e}")
        issues.append("packages.json is corrupted")
    
    # Check 3: PATH configured
    console.print("\n[bold]Checking PATH configuration...[/bold]")
    if is_in_path(CMAM_SCRIPTS):
        console.print(f"  [green]✓[/green] Scripts folder is in PATH")
    else:
        console.print(f"  [yellow]⚠[/yellow] Scripts folder is NOT in PATH")
        warnings.append("Scripts folder not in PATH")
    
    # Check 4: All registered apps have executables
    console.print("\n[bold]Checking installed apps...[/bold]")
    data = load_local_packages()
    missing_exes = []
    for app_name in data:
        exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
        if os.path.exists(exe_path):
            console.print(f"  [green]✓[/green] {app_name}.exe exists")
        else:
            console.print(f"  [red]✗[/red] {app_name}.exe is missing")
            missing_exes.append(app_name)
            issues.append(f"{app_name}.exe is missing")
    
    # Check 5: Orphaned executables
    console.print("\n[bold]Checking for orphaned executables...[/bold]")
    orphans = []
    if os.path.exists(CMAM_SCRIPTS):
        for filename in os.listdir(CMAM_SCRIPTS):
            if filename.endswith('.exe'):
                app_name = filename[:-4]
                if app_name not in data and app_name != "cmam":
                    console.print(f"  [yellow]⚠[/yellow] Orphaned: {filename}")
                    orphans.append(app_name)
                    warnings.append(f"Orphaned executable: {filename}")
    if not orphans:
        console.print(f"  [green]✓[/green] No orphaned executables")
    
    # Check 6: Network connectivity
    console.print("\n[bold]Checking network connectivity...[/bold]")
    try:
        response = requests.get("https://api.github.com", timeout=5)
        if response.status_code == 200:
            console.print(f"  [green]✓[/green] GitHub API is reachable")
        else:
            console.print(f"  [yellow]⚠[/yellow] GitHub API returned status {response.status_code}")
            warnings.append("GitHub API returned non-200 status")
    except requests.RequestException as e:
        console.print(f"  [red]✗[/red] Cannot reach GitHub API: {e}")
        issues.append("Cannot reach GitHub API")
    
    # Check 7: Remote manifest accessible
    console.print("\n[bold]Checking remote manifest...[/bold]")
    try:
        manifest = fetch_manifest()
        console.print(f"  [green]✓[/green] Remote manifest accessible ({len(manifest)} apps available)")
    except SystemExit:
        console.print(f"  [red]✗[/red] Cannot fetch remote manifest")
        issues.append("Cannot fetch remote manifest")
    
    # Check 8: Disk space
    console.print("\n[bold]Checking disk space...[/bold]")
    try:
        total, used, free = shutil.disk_usage(CMAM_ROOT)
        free_gb = free / (1024 ** 3)
        if free_gb > 1:
            console.print(f"  [green]✓[/green] {free_gb:.1f} GB free on drive")
        else:
            console.print(f"  [yellow]⚠[/yellow] Low disk space: {free_gb:.2f} GB free")
            warnings.append("Low disk space")
    except Exception:
        console.print(f"  [yellow]⚠[/yellow] Could not check disk space")
    
    # Summary
    console.print("")
    if not issues and not warnings:
        console.print(Panel(
            "[bold green]✅ All checks passed! CMAM is healthy.[/bold green]",
            title="[bold blue]Diagnostic Results[/bold blue]",
            border_style="green"
        ))
    else:
        summary_lines = []
        if issues:
            summary_lines.append(f"[red]❌ {len(issues)} issue(s) found:[/red]")
            for issue in issues:
                summary_lines.append(f"   • {issue}")
        if warnings:
            summary_lines.append(f"[yellow]⚠ {len(warnings)} warning(s):[/yellow]")
            for warning in warnings:
                summary_lines.append(f"   • {warning}")
        
        if issues:
            summary_lines.append("\n[dim]Run 'cmam repair <app>' for missing executables.[/dim]")
            summary_lines.append("[dim]Run 'cmam clean' to remove orphaned files.[/dim]")
        
        console.print(Panel(
            "\n".join(summary_lines),
            title="[bold blue]Diagnostic Results[/bold blue]",
            border_style="yellow" if not issues else "red"
        ))

@app.command()
def trust():
    """Displays the verification status of installed app signatures."""
    print_banner()
    console.print("[bold cyan]🔐 Checking trust status of installed apps...[/bold cyan]\n")
    
    data = load_local_packages()
    
    if not data:
        console.print("[yellow]📭 No apps installed.[/yellow]")
        return
    
    with console.status("[bold green]Fetching manifest and verifying...[/bold green]"):
        manifest = fetch_manifest()
    
    table = Table(title="[bold blue]Trust Status[/bold blue]")
    table.add_column("App", style="cyan")
    table.add_column("Version", style="white")
    table.add_column("Checksum", style="dim")
    table.add_column("Trust Status", style="white")
    
    for app_name, info in data.items():
        version = info.get("version", "unknown")
        exe_path = os.path.join(CMAM_SCRIPTS, f"{app_name}.exe")
        
        if not os.path.exists(exe_path):
            table.add_row(app_name, f"v{version}", "N/A", "[red]❌ Missing[/red]")
            continue
        
        local_checksum = calculate_file_checksum(exe_path)
        short_checksum = local_checksum.replace("sha256:", "")[:16] + "..."
        
        if app_name not in manifest:
            table.add_row(app_name, f"v{version}", short_checksum, "[yellow]⚠ Unknown source[/yellow]")
            continue
        
        release_info = fetch_release_info(manifest[app_name]["link"], version)
        
        if not release_info:
            table.add_row(app_name, f"v{version}", short_checksum, "[yellow]⚠ Cannot verify[/yellow]")
            continue
        
        asset = get_exe_asset(release_info)
        
        if not asset or not asset.get('checksum'):
            table.add_row(app_name, f"v{version}", short_checksum, "[yellow]⚠ No signature[/yellow]")
            continue
        
        if local_checksum == asset['checksum']:
            table.add_row(app_name, f"v{version}", short_checksum, "[green]✅ Trusted[/green]")
        else:
            table.add_row(app_name, f"v{version}", short_checksum, "[red]❌ Untrusted[/red]")
    
    console.print(table)
    console.print("\n[dim]Trust is verified by comparing SHA256 checksums with official releases.[/dim]")

@app.command()
def path(
    add: bool = typer.Option(False, "--add", "-a", help="Add scripts folder to PATH if not present.")
):
    """Checks or re-adds the install directory to your PATH."""
    print_banner()
    
    if is_in_path(CMAM_SCRIPTS):
        console.print(f"[bold green]✅ Scripts folder is already in PATH:[/bold green] {CMAM_SCRIPTS}")
    else:
        console.print(f"[bold yellow]⚠ Scripts folder is NOT in PATH:[/bold yellow] {CMAM_SCRIPTS}")
        
        if add:
            if add_folder_to_path(CMAM_SCRIPTS):
                console.print("[yellow]💡 Restart your terminal to apply PATH changes.[/yellow]")
        else:
            console.print("\n[dim]Run 'cmam path --add' to add it to your PATH.[/dim]")

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
