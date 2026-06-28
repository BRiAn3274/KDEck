import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_JSON = ROOT / "package.json"
PLUGIN_NAME = "KDEck"
FILES = (
    "plugin.json",
    "package.json",
    "main.py",
    "README.md",
    "README.zh-CN.md",
    "CHANGELOG.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
)
DIRECTORIES = ("dist", "assets", "defaults", "py_modules", "backend/src")
EXCLUDED_DIR_NAMES = {"__pycache__"}
EXCLUDED_SUFFIXES = (".map", ".pyc")
EXCLUDED_FILES = {"backend/src/kdeck_updater.py"}
REQUIRED_ZIP_ENTRIES = (
    "KDEck/plugin.json",
    "KDEck/package.json",
    "KDEck/main.py",
    "KDEck/dist/index.js",
    "KDEck/assets/logo.png",
    "KDEck/py_modules/.keep",
    "KDEck/backend/src/kdeck_backend.py",
    "KDEck/backend/src/kdeck_kde_receiver.py",
)


def run_build() -> None:
    command = ["pnpm.cmd" if os.name == "nt" else "pnpm", "build"]
    result = subprocess.run(command, cwd=ROOT, text=True)
    if result.returncode != 0:
        raise SystemExit(f"Frontend build failed with exit code {result.returncode}.")


def validate_release_zip(zip_path: Path) -> None:
    """Validate the minimal file set Decky needs to load the packaged plugin."""
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    missing = [entry for entry in REQUIRED_ZIP_ENTRIES if entry not in names]
    if missing:
        formatted = "\n".join(f"- {entry}" for entry in missing)
        raise SystemExit(f"Release zip is missing required entries:\n{formatted}")


def validate_packaged_version(zip_path: Path, expected_version: str) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        package = json.loads(archive.read(f"{PLUGIN_NAME}/package.json").decode("utf-8"))
    packed_version = package.get("version")
    if packed_version != expected_version:
        raise SystemExit(f"Packaged version {packed_version} does not match package.json {expected_version}.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    args = sys.argv[1:]
    skip_build = "--skip-build" in args
    version_args = [arg for arg in args if arg != "--skip-build"]
    version = version_args[0] if version_args else package["version"]
    if not skip_build:
        run_build()

    dist_index = ROOT / "dist" / "index.js"
    if not dist_index.exists():
        raise SystemExit("dist/index.js does not exist. Run pnpm run build first.")

    release_dir = ROOT / "release"
    release_dir.mkdir(exist_ok=True)
    zip_path = release_dir / f"{PLUGIN_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name in FILES:
            source = ROOT / file_name
            if not source.exists():
                raise SystemExit(f"Required release file is missing: {file_name}")
            archive.write(source, f"{PLUGIN_NAME}/{file_name}")
        for directory in DIRECTORIES:
            source_dir = ROOT / directory
            if not source_dir.exists():
                continue
            for source in source_dir.rglob("*"):
                if source.is_dir():
                    continue
                if any(part in EXCLUDED_DIR_NAMES for part in source.relative_to(ROOT).parts):
                    continue
                if source.suffix in EXCLUDED_SUFFIXES:
                    continue
                relative = source.relative_to(ROOT).as_posix()
                if relative in EXCLUDED_FILES:
                    continue
                archive.write(source, f"{PLUGIN_NAME}/{relative}")

    validate_release_zip(zip_path)
    validate_packaged_version(zip_path, version)
    print(zip_path)
    print(f"SHA256: {sha256_file(zip_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

