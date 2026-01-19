# CMAM - Connor Merk App Manager

[![Windows](https://img.shields.io/badge/platform-Windows-blue)](https://github.com/cmerk2021/cmam)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A lightweight package manager for installing and managing Connor Merk's applications on Windows.

## ✨ Features

- **Simple Installation** - One-command install for supported applications
- **Automatic PATH Management** - Apps are automatically added to your PATH
- **Version Control** - Install specific versions or update to the latest
- **Checksum Verification** - Ensures downloaded binaries are authentic
- **Self-Updating** - Keep CMAM itself up to date

## 📦 Installation

### Quick Install (Recommended)

Run the following command in PowerShell:

```powershell
# Download the installer
Invoke-WebRequest -Uri "https://github.com/cmerk2021/cmam/releases/latest/download/install.exe" -OutFile "install.exe"

# Run the installer
.\install.exe
```

Or, alternatively download and run the installer executable from the latest release or the /dist directory.

### Installer Options

| Option | Description |
|--------|-------------|
| `--version`, `-v` | Install a specific version of CMAM |
| `--skip-path` | Skip adding CMAM to PATH |
| `--force`, `-f` | Force reinstall even if already installed |

### Manual Installation

1. Download `cmam.exe` from the [latest release](https://github.com/cmerk2021/cmam/releases/latest)
2. Create the directory `C:\.cmam\scripts`
3. Place `cmam.exe` in `C:\.cmam\scripts`
4. Add `C:\.cmam\scripts` to your PATH environment variable
5. Restart your terminal

### Updating

To update CMAM when installed, simply run:

```
cmam self-update
```

## 🚀 Usage

### Installing an Application

```bash
# Install the latest version
cmam install <app-name>

# Install a specific version
cmam install <app-name> --version 1.2.0
```

### Updating an Application

```bash
# Update to the latest version
cmam update <app-name>

# Update to a specific version
cmam update <app-name> --version 2.0.0

# Keep a backup of the old version
cmam update <app-name> --keep-backup
```

### Other Commands

| Command | Description |
|---------|-------------|
| `cmam install <app>` | Install an application |
| `cmam update <app>` | Update an installed application |
| `cmam uninstall <app>` | Uninstall an application |
| `cmam list` | List all installed applications |
| `cmam search` | Search for available applications |
| `cmam info <app>` | Show details about an application |
| `cmam self-update` | Update CMAM itself |
| `cmam doctor` | Run health diagnostics |
| `cmam clean` | Clean up cache and temp files |

> **Note:** Some commands are still in development. Run `cmam --help` to see all available commands.

## 📁 Directory Structure

CMAM installs to the following locations:

```
C:\.cmam\
├── scripts\          # Installed application executables
│   └── cmam.exe      # CMAM itself
├── .cache\           # Temporary download cache
├── packages.json     # Installed packages metadata
└── packages.txt      # Package list (legacy)
```

## 🔧 Configuration

CMAM stores its configuration and installed packages metadata in `C:\.cmam\packages.json`.

## 🛠️ Troubleshooting

### CMAM is not recognized as a command

1. Ensure `C:\.cmam\scripts` is in your PATH
2. Restart your terminal after installation
3. Run `cmam path` to verify or fix PATH configuration

### Download fails or checksum mismatch

1. Check your internet connection
2. Try again - the server may have been temporarily unavailable
3. Run `cmam doctor` to diagnose issues

### Permission errors

Some operations may require administrator privileges. Try running your terminal as Administrator.

## 📄 License

Copyright (c) 2026 Connor Merk. All rights reserved.

## 🔗 Links

- [GitHub Repository](https://github.com/cmerk2021/cmam)
- [Issue Tracker](https://github.com/cmerk2021/cmam/issues)
- [Releases](https://github.com/cmerk2021/cmam/releases)
