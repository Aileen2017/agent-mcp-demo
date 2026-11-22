"""Build the zip package that runs the flight MCP, calendar MCP and agent API on AWS Lambda.

Output: build/lambda/mcp-demo-lambda.zip (read by infra/terraform/lambda, which uploads it to S3).

Dependencies are resolved for Lambda's Linux x86_64 platform with uv, so this works from
Windows or macOS without Docker. uv must be on PATH: https://docs.astral.sh/uv/

    python scripts/build_lambda_zip.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = REPO_ROOT / "build" / "lambda"
PACKAGE_DIR = BUILD_DIR / "package"
ZIP_PATH = BUILD_DIR / "mcp-demo-lambda.zip"

# Lambda's Python runtime version and platform (must match the runtime in infra/terraform/lambda).
PYTHON_VERSION = "3.13"
PYTHON_PLATFORM = "x86_64-manylinux_2_28"

# Lambda's limit on the unzipped size of a deployment package, including layers.
UNZIPPED_LIMIT_BYTES = 250 * 1024 * 1024

# App code copied into the zip root. Paths inside the zip match the import paths the app uses.
APP_DIRS = ["agent", "servers"]
APP_FILES = {
    "lambda/lambda_handlers.py": "lambda_handlers.py",
    "lambda/run.sh": "run.sh",
}
EXCLUDED_NAMES = {"__pycache__", "tests"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def install_dependencies() -> None:
    if shutil.which("uv") is None:
        sys.exit("uv is not on PATH. Install it from https://docs.astral.sh/uv/ and rerun.")

    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python-platform",
            PYTHON_PLATFORM,
            "--python-version",
            PYTHON_VERSION,
            "--target",
            str(PACKAGE_DIR),
            "--only-binary",
            ":all:",
            "-r",
            str(REPO_ROOT / "lambda" / "requirements.txt"),
        ],
        check=True,
    )


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDED_NAMES for part in path.parts) or path.suffix in EXCLUDED_SUFFIXES


def add_file(archive: zipfile.ZipFile, source: Path, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname)
    info.compress_type = zipfile.ZIP_DEFLATED
    # Keep the executable bit for the entry script; Lambda runs it through the adapter.
    mode = 0o755 if source.suffix == ".sh" else 0o644
    info.external_attr = (0o100000 | mode) << 16
    archive.writestr(info, source.read_bytes())


def write_zip() -> None:
    ZIP_PATH.unlink(missing_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w") as archive:
        for path in sorted(PACKAGE_DIR.rglob("*")):
            if path.is_file() and not should_skip(path.relative_to(PACKAGE_DIR)):
                add_file(archive, path, path.relative_to(PACKAGE_DIR).as_posix())

        for dir_name in APP_DIRS:
            for path in sorted((REPO_ROOT / dir_name).rglob("*")):
                rel = path.relative_to(REPO_ROOT)
                if path.is_file() and not should_skip(rel):
                    add_file(archive, path, rel.as_posix())

        for source_name, arcname in APP_FILES.items():
            add_file(archive, REPO_ROOT / source_name, arcname)


def main() -> None:
    if PACKAGE_DIR.exists():
        shutil.rmtree(PACKAGE_DIR)
    PACKAGE_DIR.mkdir(parents=True)

    install_dependencies()
    write_zip()

    unzipped = sum(
        info.file_size for info in zipfile.ZipFile(ZIP_PATH).infolist()
    )
    zipped = ZIP_PATH.stat().st_size
    print(f"Wrote {ZIP_PATH}")
    print(f"  zipped:   {zipped / 1048576:.1f} MB")
    print(f"  unzipped: {unzipped / 1048576:.1f} MB (limit 250 MB)")
    if unzipped > UNZIPPED_LIMIT_BYTES:
        sys.exit("Unzipped package is over Lambda's 250 MB limit. Trim dependencies.")


if __name__ == "__main__":
    main()
