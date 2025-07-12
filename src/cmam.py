# CMAM - Connor Merk App Manager
# Package manager for installing and managing Connor Merk's applications.
# Copyright (c) 2025 Connor Merk
# VERSION: 1.2.0

# COMMANDS: ------------------------------------------------------------------------------
#           install     Install an app with latest or specified version
#           update      	Update an app to the latest or specific version
#           uninstall   Uninstall a currently installed app
#           list        List installed apps with versions
#           info        Shows details about an app
#           search      Search available apps in the online manifest
#           self-update Update CMAM
#           ------------------------------------------------------------------------------
#           repair      Uninstall and reinstall a corrupted app
#           validate    Check if all installed apps have expected checksums
#           clean       Remove .cache folder, purge temp files, or uninstall orphaned apps
#           doctor      Run a quick diagnostic on path, folders, config health
#           ------------------------------------------------------------------------------
#           verify      Manually verify checksum of an installed app
#           trust       Display whether checksum/signature matches verified release
#           ------------------------------------------------------------------------------
#           path        Re-add the install folder to PATH or check if it's present
#           export      Export installed apps as a manifest file
#           import      Import apps to install from a manifest file
#           rollback    Downgrade to a previous version

import os
import sys
import winreg
import requests
from requests.exceptions import HTTPError
import json
import base64
import typer
import hashlib
import ctypes
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TimeRemainingColumn

console = Console()
app = typer.Typer(
    help="CMAM: Connor Merk App Manager - Your package manager for Connor Merk's apps.",
    no_args_is_help=True
)

# ═══════════════════════════════════════════════
# PATH HANDLING
# ═════════════════════════════════════════════

already_in_path = False

def add_folder_to_path(folder_path: str) -> bool:
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

# ═════════════════════════════════════════════
# INSTALL COMMAND
# ═════════════════════════════════════════════

@app.command()
def install(
    app_name: str = typer.Argument(..., help="Name of the application to install."),
    version: str = typer.Option(None, "--version", "-v", help="Specify a version to install.")
):
    """Installs a specified application from the CMAM repository."""

    console.print(f"[bold cyan]🔧 Installing [green]{app_name}[/green]"
                  + (f" [magenta](v{version})[/magenta]" if version else "") + "...[/bold cyan]")

    with console.status("[bold green]Preparing installation...[/bold green]") as status:
        if os.path.exists(rf"C:\\.cmam\\scripts\\{app_name}.exe"):
            console.print(f"[bold red]⚠ App [blue]{app_name}[/blue] is already installed. Use [bold blue]update[/bold blue] instead.[/bold red]")
            raise typer.Exit(code=1)

        for folder in [r"C:\\.cmam", r"C:\\.cmam\\.cache", r"C:\\.cmam\\scripts"]:
            os.makedirs(folder, exist_ok=True)

        packages_file = r"C:\\.cmam\\packages.txt"
        if not os.path.exists(packages_file):
            open(packages_file, 'w').close()

        # Fetch application manifest
        status.update("[bold green]Fetching application manifest...[/bold green]")
        request_url = "https://api.github.com/repos/cmerk2021/cmam/contents/packages.json"
        try:
            response = requests.get(request_url)
            response.raise_for_status()
            manifest_data = response.json()
            if manifest_data.get('type') == 'file' and 'content' in manifest_data:
                decoded = base64.b64decode(manifest_data['content']).decode('utf-8')
                app_data = json.loads(decoded)
                if app_name not in app_data:
                    console.print(f"[bold red]❌ App [blue]{app_name}[/blue] not found in manifest.[/bold red]")
                    raise typer.Exit(code=1)
                app_data = app_data[app_name]
            else:
                console.print("[bold red]❌ Invalid or missing 'packages.json' in GitHub repo.[/bold red]")
                raise typer.Exit(code=1)
        except requests.RequestException as e:
            console.print(f"[bold red]🌐 Network error: {e}[/bold red]")
            raise typer.Exit(code=1)
        except json.JSONDecodeError:
            console.print("[bold red]❌ Error parsing 'packages.json'.[/bold red]")
            raise typer.Exit(code=1)

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

        tmp_path = rf"C:\\.cmam\\scripts\\{app_name}.exe.tmp"
        exe_path = rf"C:\\.cmam\\scripts\\{app_name}.exe"

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
        add_folder_to_path(r"C:\\.cmam\\scripts")

        # Update local package record
        status.update("[bold green]Saving metadata...[/bold green]")
        try:
            with open(r"C:\\.cmam\\packages.json", "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        data[app_name] = {"version": app_version.replace("v", "")}
        with open(r"C:\\.cmam\\packages.json", "w") as f:
            json.dump(data, f, indent=2)

    # Completion
    console.print(Panel(
        f"[bold green]✅ {app_name} v{app_version.replace('v','')} installed successfully![/bold green]\n\n"
        "You can now run your app from any terminal window.",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green"
    ))
    if not already_in_path: console.print("[yellow]💡 Tip: Restart your terminal to apply PATH changes.[/yellow]")

@app.command()
def update():
    """Updates an installed app to the latest or specified version."""
    pass

@app.command()
def uninstall():
    """Uninstalls a currently installed app."""
    pass

@app.command()
def list():
    """Lists all installed apps with their versions."""
    pass

@app.command()
def info():
    """Shows detailed info about a specified app."""
    pass

@app.command()
def search():
    """Searches for apps available in the remote repository."""
    pass

@app.command()
def self_update():
    """Updates CMAM."""
    pass

@app.command()
def repair():
    """Repairs a corrupted app by uninstalling and reinstalling it."""
    pass

@app.command()
def validate():
    """Checks if all installed apps match their expected checksums."""
    pass

@app.command()
def clean():
    """Cleans up cache files, temp data, and optionally orphaned apps."""
    pass

@app.command()
def doctor():
    """Runs a health diagnostic on environment and configuration."""
    pass

@app.command()
def verify():
    """Verifies the checksum of a specified installed app."""
    pass

@app.command()
def trust():
    """Displays the verification status of installed app signatures."""
    pass

@app.command()
def path():
    """Checks or re-adds the install directory to your PATH."""
    pass

@app.command()
def export():
    """Exports the list of installed apps to a manifest file."""
    pass

@app.command()
def import_():
    """Installs all apps listed in a provided manifest file."""
    pass

@app.command()
def rollback():
    """Rolls back an app to a previous installed version."""
    pass

# ═════════════════════════════════════════════
# DUMMY COMMAND FOR TESTING
# ═════════════════════════════════════════════

@app.command()
def hello():
    """Says hello. Placeholder command."""
    console.print("[green]👋 Hello from CMAM![/green]")

# ═════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════

if __name__ == "__main__":
    app()
