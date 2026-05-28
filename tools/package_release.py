import json
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
    "kdeck_backend.py",
    "kdeck_kde_receiver.py",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
)
DIRECTORIES = ("dist", "assets", "defaults", "py_modules")
EXCLUDED_SUFFIXES = (".map",)


def main() -> int:
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    version = sys.argv[1] if len(sys.argv) > 1 else package["version"]

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
            archive.write(source, f"{PLUGIN_NAME}/{file_name}")
        for directory in DIRECTORIES:
            source_dir = ROOT / directory
            if not source_dir.exists():
                continue
            for source in source_dir.rglob("*"):
                if source.is_dir():
                    continue
                if source.suffix in EXCLUDED_SUFFIXES:
                    continue
                relative = source.relative_to(ROOT).as_posix()
                archive.write(source, f"{PLUGIN_NAME}/{relative}")

    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

