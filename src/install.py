# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  CMAM Installer                                                            ║
# ║  Installs CMAM to C:\.cmam\scripts and adds it to PATH                     ║
# ║  Copyright (c) 2025 Connor Merk                                            ║
# ╚════════════════════════════════════════════════════════════════════════════╝

import os
import sys
import ctypes
import winreg
import hashlib
import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn, TimeRemainingColumn

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  CONSTANTS                                                                 ║
# ╚════════════════════════════════════════════════════════════════════════════╝

CMAM_ROOT = r"C:\.cmam"
CMAM_CACHE = os.path.join(CMAM_ROOT, ".cache")
CMAM_SCRIPTS = os.path.join(CMAM_ROOT, "scripts")
CMAM_EXE_PATH = os.path.join(CMAM_SCRIPTS, "cmam.exe")
GITHUB_RELEASES_API = "https://api.github.com/repos/cmerk2021/cmam/releases/latest"

console = Console()
app = typer.Typer(
    help="CMAM Installer - Installs the Connor Merk App Manager to your system.",
    no_args_is_help=False
)

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  HELPER FUNCTIONS                                                          ║
# ╚════════════════════════════════════════════════════════════════════════════╝

def print_banner():
    """Print the installer banner."""
    console.print(Panel(
        "[bold blue]CMAM Installer[/bold blue]\n"
        "[green]Connor Merk App Manager[/green]\n"
        "[dim]https://github.com/cmerk2021/cmam[/dim]",
        border_style="blue",
        expand=False
    ))
    console.print()

def is_admin() -> bool:
    """Check if the script is running with admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ensure_directories():
    """Create required directories if they don't exist."""
    console.print("[bold cyan]📁 Creating directories...[/bold cyan]")
    for folder in [CMAM_ROOT, CMAM_CACHE, CMAM_SCRIPTS]:
        os.makedirs(folder, exist_ok=True)
        console.print(f"   [green]✓[/green] {folder}")
    console.print()

def add_to_path(folder_path: str) -> bool:
    """Add folder to user PATH if not already present."""
    folder_path = os.path.abspath(folder_path)
    console.print(f"[bold cyan]🔧 Configuring PATH...[/bold cyan]")

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0,
            winreg.KEY_ALL_ACCESS
        )

        try:
            current_path, reg_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_path = ""
            reg_type = winreg.REG_EXPAND_SZ

        paths = [p.strip() for p in current_path.split(';') if p.strip()]
        normalized_paths = [os.path.normpath(p).lower() for p in paths]

        if folder_path.lower() in normalized_paths:
            console.print(f"   [green]✓[/green] Already in PATH")
            winreg.CloseKey(key)
            return True

        new_path = f"{current_path};{folder_path}" if current_path else folder_path
        winreg.SetValueEx(key, "Path", 0, reg_type, new_path)
        winreg.CloseKey(key)

        # Broadcast environment change
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 5000, None
        )

        console.print(f"   [green]✓[/green] Added to PATH")
        return True

    except PermissionError:
        console.print(f"   [red]✗[/red] Permission denied. Try running as administrator.")
        return False
    except Exception as e:
        console.print(f"   [red]✗[/red] Error modifying PATH: {e}")
        return False

def download_cmam(version: str = None) -> bool:
    """Download the CMAM executable from GitHub releases."""
    console.print("[bold cyan]📥 Fetching release information...[/bold cyan]")

    try:
        if version:
            api_url = f"https://api.github.com/repos/cmerk2021/cmam/releases/tags/v{version}"
        else:
            api_url = GITHUB_RELEASES_API

        response = requests.get(api_url)
        response.raise_for_status()
        release_data = response.json()
    except requests.HTTPError as e:
        if response.status_code == 404:
            console.print(f"   [red]✗[/red] Version '{version}' not found.")
        else:
            console.print(f"   [red]✗[/red] HTTP error: {e}")
        return False
    except requests.RequestException as e:
        console.print(f"   [red]✗[/red] Network error: {e}")
        return False

    release_version = release_data.get("tag_name", "unknown")
    console.print(f"   [green]✓[/green] Found version: [magenta]{release_version}[/magenta]")

    # Find the .exe asset
    exe_url = None
    checksum = None
    for asset in release_data.get("assets", []):
        name = asset.get("name", "").lower()
        if name == "cmam.exe" or name.endswith(".exe"):
            exe_url = asset.get("browser_download_url")
            checksum = asset.get("digest")
            break

    if not exe_url:
        console.print("   [red]✗[/red] No executable found in release assets")
        return False

    console.print()
    console.print("[bold cyan]⬇️  Downloading CMAM...[/bold cyan]")

    try:
        sha256 = hashlib.sha256()
        tmp_path = CMAM_EXE_PATH + ".tmp"

        with requests.get(exe_url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('Content-Length', 0))

            with open(tmp_path, 'wb') as f, Progress(
                SpinnerColumn(),
                TextColumn("[cyan]{task.description}[/cyan]"),
                BarColumn(),
                DownloadColumn(),
                TimeRemainingColumn(),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Downloading...", total=total_size)
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        sha256.update(chunk)
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))

        console.print(f"   [green]✓[/green] Download complete ({total_size / 1024 / 1024:.2f} MB)")

        # Verify checksum if provided
        if checksum:
            expected = checksum.replace("sha256:", "")
            actual = sha256.hexdigest()
            if expected != actual:
                console.print("   [red]✗[/red] Checksum verification failed!")
                os.remove(tmp_path)
                return False
            console.print("   [green]✓[/green] Checksum verified")
        else:
            console.print("   [yellow]⚠[/yellow] No checksum provided, skipping verification")

        # Move to final location
        if os.path.exists(CMAM_EXE_PATH):
            os.remove(CMAM_EXE_PATH)
        os.rename(tmp_path, CMAM_EXE_PATH)
        console.print(f"   [green]✓[/green] Installed to [dim]{CMAM_EXE_PATH}[/dim]")

        return True

    except requests.RequestException as e:
        console.print(f"   [red]✗[/red] Download failed: {e}")
        return False
    except IOError as e:
        console.print(f"   [red]✗[/red] File error: {e}")
        return False

def verify_installation() -> bool:
    """Verify that CMAM was installed correctly."""
    console.print()
    console.print("[bold cyan]🔍 Verifying installation...[/bold cyan]")

    if os.path.exists(CMAM_EXE_PATH):
        size = os.path.getsize(CMAM_EXE_PATH)
        console.print(f"   [green]✓[/green] cmam.exe exists ({size / 1024:.1f} KB)")
        return True
    else:
        console.print("   [red]✗[/red] cmam.exe not found")
        return False

def print_success(path_updated: bool):
    """Print success message and next steps."""
    console.print()
    console.print(Panel(
        "[bold green]✅ CMAM installed successfully![/bold green]\n\n"
        "[white]Next steps:[/white]\n"
        "  1. Restart your terminal (or open a new one)\n"
        "  2. Run [cyan]cmam --help[/cyan] to see available commands\n"
        "  3. Run [cyan]cmam install <app>[/cyan] to install an application\n\n"
        "[dim]For more information: https://github.com/cmerk2021/cmam[/dim]",
        title="[bold blue]CMAM[/bold blue]",
        border_style="green",
        expand=False
    ))
    if path_updated:
        console.print("[yellow]💡 Tip: Restart your terminal to apply PATH changes.[/yellow]")

def print_failure():
    """Print failure message."""
    console.print()
    console.print(Panel(
        "[bold red]❌ Installation Failed[/bold red]\n\n"
        "Please check the errors above and try again.\n"
        "If the problem persists, please open an issue at:\n"
        "[cyan]https://github.com/cmerk2021/cmam/issues[/cyan]",
        title="[bold blue]CMAM[/bold blue]",
        border_style="red",
        expand=False
    ))

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  MAIN COMMAND                                                              ║
# ╚════════════════════════════════════════════════════════════════════════════╝

@app.callback(invoke_without_command=True)
def main(
    version: str = typer.Option(None, "--version", "-v", help="Specify a version to install."),
    skip_path: bool = typer.Option(False, "--skip-path", help="Skip adding CMAM to PATH."),
    force: bool = typer.Option(False, "--force", "-f", help="Force reinstall even if already installed."),
):
    """
    Installs CMAM (Connor Merk App Manager) to your system.
    
    This will:
    - Create C:\\.cmam directories
    - Download the latest CMAM executable
    - Add CMAM to your PATH
    """
    print_banner()

    # Check for Windows
    if sys.platform != "win32":
        console.print("[bold red]❌ CMAM is currently only supported on Windows.[/bold red]")
        raise typer.Exit(code=1)

    # Check if already installed
    if os.path.exists(CMAM_EXE_PATH) and not force:
        console.print(f"[bold yellow]⚠ CMAM is already installed at [cyan]{CMAM_EXE_PATH}[/cyan][/bold yellow]")
        console.print("[dim]Use --force to reinstall.[/dim]")
        raise typer.Exit(code=0)

    success = True
    path_was_updated = False

    # Step 1: Create directories
    try:
        ensure_directories()
    except Exception as e:
        console.print(f"[bold red]❌ Failed to create directories: {e}[/bold red]")
        success = False

    # Step 2: Download CMAM
    if success:
        if not download_cmam(version):
            success = False

    # Step 3: Add to PATH
    if success and not skip_path:
        console.print()
        result = add_to_path(CMAM_SCRIPTS)
        if not result:
            console.print("[yellow]⚠ PATH not updated. You may need to add it manually.[/yellow]")
        else:
            path_was_updated = True

    # Step 4: Verify
    if success:
        if not verify_installation():
            success = False

    # Final message
    if success:
        print_success(path_was_updated)
        raise typer.Exit(code=0)
    else:
        print_failure()
        raise typer.Exit(code=1)

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  ENTRY POINT                                                               ║
# ╚════════════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    app()
