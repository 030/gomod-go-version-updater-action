import logging
import os
import re
import requests
import sys
from pathlib import Path
from typing import Tuple

DOCKERFILE = "Dockerfile"
GO_MOD_FILE = "go.mod"
GO_MOD_GO_VERSION_REGEX = r"go\s\d+.*"
GO_VERSIONS_URL = "https://go.dev/dl/?mode=json"
LOGGING_LEVEL = os.getenv(
    "GOMOD_GO_VERSION_UPDATER_ACTION_LOGGING_LEVEL", logging.INFO
)


def configure_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_latest_go_version():
    try:
        response = requests.get(GO_VERSIONS_URL)
        response.raise_for_status()
        data = response.json()
        match = re.match(r"go(\d+)\.(\d+)\.(\d+)", data[0]["version"])
        return match.groups() if match else ("", "", "")
    except requests.RequestException as e:
        logging.error(f"Error fetching data from {GO_VERSIONS_URL}: {e}")
        sys.exit(1)


def get_go_version_from_mod_file(go_mod_file: str) -> Tuple[str, bool]:
    if not os.path.exists(go_mod_file):
        logging.error(f"The file '{go_mod_file}' does not exist.")
        return "", False

    with open(go_mod_file, "r") as file:
        content = file.read()
        match = re.search(r"go\s(\d+)\.(\d+)\.?(\d+)?", content)
        if not match:
            raise ValueError(f"No Go version defined in file: {go_mod_file}")
        major, minor, patch = match.groups()
        version = f"{major}.{minor}" + (f".{patch}" if patch else "")
        return version, bool(patch)


def update_go_version_in_mod_file(
    go_mod_file: str, current_version: str, new_version: str
):
    try:
        with open(go_mod_file, "r") as file:
            content = file.read()
        content = re.sub(GO_MOD_GO_VERSION_REGEX, f"go {new_version}", content)
        with open(go_mod_file, "w") as file:
            file.write(content)
        logging.info(
            f"bump golang version from {current_version} to {new_version}"
        )
    except FileNotFoundError:
        logging.info(f"File not found: {go_mod_file}")


def update_go_version_in_directory(
    new_major: str,
    new_minor: str,
    new_patch: str,
    dir: str = None,
):
    if dir is None:
        dir = os.getcwd()
    for path in Path(dir).rglob(GO_MOD_FILE):
        logging.debug(f"Found go.mod file: {path}")
        current_version, has_patch = get_go_version_from_mod_file(path)
        new_major_minor = f"{new_major}.{new_minor}"
        if has_patch:
            update_go_version_in_mod_file(
                path,
                current_version,
                f"{new_major_minor}.{new_patch}",
            )
            continue
        update_go_version_in_mod_file(
            path, current_version, f"{new_major_minor}"
        )


def update_dockerfile_version_in_directory(
    new_major: str, new_minor: str, new_patch: str
):
    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            if file == DOCKERFILE:
                dockerfile_path = os.path.join(root, file)
                update_dockerfile_version(
                    dockerfile_path,
                    new_major,
                    new_minor,
                    new_patch,
                )


def update_dockerfile_version(
    dockerfile_path: str, new_major: str, new_minor: str, new_patch: str
):
    with open(dockerfile_path, "r") as file:
        lines = file.readlines()

    updated_lines = []
    three_digit_pattern = re.compile(r"FROM\sgolang:(\d+\.\d+\.\d+)")
    two_digit_pattern = re.compile(r"FROM\sgolang:(\d+\.\d+)")

    for line in lines:
        match = three_digit_pattern.search(line) or two_digit_pattern.search(
            line
        )
        if match:
            version = match.group(1)
            new_version = (
                f"{new_major}.{new_minor}.{new_patch}"
                if "." in version
                else f"{new_major}.{new_minor}"
            )
            updated_lines.append(line.replace(version, new_version))
        else:
            updated_lines.append(line)

    with open(dockerfile_path, "w") as file:
        file.writelines(updated_lines)
    logging.info(
        f"Updated Dockerfile to version {new_major}.{new_minor}.{new_patch}"
    )


def main():
    configure_logging(LOGGING_LEVEL)
    latest_major, latest_minor, latest_patch = get_latest_go_version()

    update_dockerfile_version_in_directory(
        latest_major, latest_minor, latest_patch
    )

    update_go_version_in_directory(latest_major, latest_minor, latest_patch)


if __name__ == "__main__":
    main()
