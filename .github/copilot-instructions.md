# Copilot Instructions for CMAM

This repository contains CMAM (Connor Merk App Manager), a single-file Python package manager.

## Project Structure

- The project is single-file.
- The main and only source file is: `src/cmam.py`
- The version is defined as a string in:
  
  CMAM_VERSION = "MAJOR.MINOR.PATCH"

- `CMAM_VERSION` is the single source of truth for the application version.

---

# Versioning Rules (MANDATORY)

Copilot MUST automatically update `CMAM_VERSION` whenever modifying logic in `src/cmam.py`.

Versioning follows strict Semantic Versioning:

MAJOR.MINOR.PATCH

## PATCH bump (x.y.Z → x.y.Z+1)

Use when:
- Fixing bugs
- Correcting logic errors
- Improving reliability
- Refactoring without changing behavior
- Performance improvements that do not change outcomes

## MINOR bump (x.Y.z → x.Y+1.0)

Use when:
- Adding a new command
- Adding a new optional flag
- Adding new backward-compatible features
- Expanding functionality without breaking existing behavior

## MAJOR bump (X.y.z → X+1.0.0)

Use when making breaking changes, including but not limited to:

- Removing or renaming commands
- Renaming flags or changing flag behavior
- Changing required arguments
- Changing default behavior in a way that affects scripts
- Changing exit codes
- Changing machine-parseable output format
- Changing manifest/export/import schema
- Changing configuration structure
- Changing install directory structure
- Altering dependency resolution logic in a non-backward-compatible way

---

# Automatic Behavior Requirement

When modifying `src/cmam.py`, Copilot MUST:

1. Determine whether the change is PATCH, MINOR, or MAJOR.
2. Update `CMAM_VERSION` accordingly in the same edit.
3. Reset lower-order fields when required:
   - MAJOR bump → reset MINOR and PATCH to 0
   - MINOR bump → reset PATCH to 0

Copilot must not leave the version unchanged if logic has changed.

---

# Code Quality Rules

- Python 3.11+ only
- Use type hints where appropriate
- No placeholder code
- No TODO comments
- Production-ready code only
- Maintain CLI backward compatibility unless explicitly performing a breaking change

---

# Architectural Constraints

- Single-file design must be preserved.
- Do not split into multiple modules.
- Do not introduce unnecessary dependencies.

---

Copilot must treat this file as authoritative.
