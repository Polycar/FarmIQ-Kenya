# FarmIQ Phase 11: Project Export to Local Disk D

This phase involves migrating the entire FarmIQ codebase and development history to the user's preferred local storage at `D:\farm IQ`.

## Proposed Changes

### 1. File Migration [COPY]
- **Source**: `C:\Users\Khal\.gemini\antigravity\scratch\FarmIQ\`
- **Destination**: `D:\farm IQ\`
- **Files to Copy**:
  - `app.py`, `recommender.py`, `database.py`, `dealers.py`, `report_gen.py`, `requirements.txt`.
  - `extract_soil_data.py`, `mock_soil_data.py`.
  - Entire `data/` directory (containing `kenya_county_soils.csv`).
  - **Note**: The `venv` directory will *not* be copied to keep the folder clean and avoid path breakage. The user can recreate it using `requirements.txt`.

### 2. Documentation Migration [COPY/NEW]
- **Source**: Artifacts directory.
- **Destination**: `D:\farm IQ\docs\`
- **Files to Copy**:
  - `walkthrough.md`, `task.md`, `implementation_plan.md`.

## User Review Required

> [!IMPORTANT]
> **Drive Access**: I am assuming I have write access to `D:\`. If the operation fails due to permissions, please let me know.

## Verification Plan
1. Execute recursive copy commands.
2. List the full directory tree of `D:\farm IQ` to confirm successful migration of all 10+ core files and documentation.
