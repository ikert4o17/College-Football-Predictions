"""Package local Project Gridiron generated state for one-time GitHub sync.

This does NOT include secrets, virtual environments, .git metadata, or Python
cache files. It packages generated data that may exist only on the Mac so it
can be uploaded once and committed into GitHub as the canonical project store.

Usage:
    python3 -m data.package_local_state

Output:
    project_gridiron_local_state.zip
"""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "project_gridiron_local_state.zip"

INCLUDE_PATHS = [
    ROOT / "data" / "raw",
    ROOT / "data" / "processed",
    ROOT / "site_data",
]

EXCLUDED_NAMES = {".DS_Store", "__pycache__"}


def should_include(path: Path) -> bool:
    return not any(part in EXCLUDED_NAMES for part in path.parts)


def main():
    files = []
    for base in INCLUDE_PATHS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and should_include(path):
                files.append(path)

    files.sort()

    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))

    total_bytes = sum(path.stat().st_size for path in files)

    print("=" * 78)
    print("PROJECT GRIDIRON LOCAL STATE PACKAGE")
    print("=" * 78)
    print(f"Files packaged: {len(files)}")
    print(f"Uncompressed size: {total_bytes / (1024 * 1024):.1f} MB")
    print(f"Archive: {OUTPUT}")
    print("\nUpload this ZIP to ChatGPT. The repository can then be synchronized")
    print("without requiring GitHub authentication on this Mac.")


if __name__ == "__main__":
    main()
