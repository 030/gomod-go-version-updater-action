import hashlib
import logging
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

DOCKERFILE = "Dockerfile"
GO_MOD_FILE = "go.mod"
GO_MOD_GO_VERSION_REGEX = r"go\s\d+.*"
GO_VERSIONS_URL = "https://go.dev/dl/?mode=json"
LOGGING_LEVEL = os.getenv(
    "GOMOD_GO_VERSION_UPDATER_ACTION_LOGGING_LEVEL", logging.INFO
)

DOCKER_AUTH_URL = "https://auth.docker.io/token"
DOCKER_AUTH_SERVICE = "registry.docker.io"
DOCKER_REGISTRY_URL = "https://registry-1.docker.io"
GOLANG_IMAGE_REPOSITORY = "library/golang"
MANIFEST_MEDIA_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)
MANIFEST_ACCEPT = ",".join(MANIFEST_MEDIA_TYPES)
HTTP_TIMEOUT = 30

DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")

# A `FROM golang:<version><variant>[@sha256:<digest>]` line. The variant, e.g.
# `-alpine`, and an optional digest pin are captured so that they survive - or,
# for the digest, get updated by - a version bump.
FROM_GOLANG_PATTERN = re.compile(
    r"(?P<prefix>FROM\s+(?:--\S+\s+)*golang:)"
    r"(?P<version>\d+\.\d+(?:\.\d+)?)"
    r"(?P<variant>[\w.\-]*)"
    r"(?:@sha256:(?P<digest>[0-9a-f]{64}))?"
)


class DigestResolutionError(Exception):
    """Raised when the digest of a golang image tag cannot be determined."""


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
    dir: str = "",
):
    if dir == "":
        dir = os.getcwd()
    for path in Path(dir).rglob(GO_MOD_FILE):
        logging.debug(f"Found go.mod file: {path}")
        current_version, has_patch = get_go_version_from_mod_file(str(path))
        new_major_minor = f"{new_major}.{new_minor}"
        if has_patch:
            update_go_version_in_mod_file(
                str(path),
                current_version,
                f"{new_major_minor}.{new_patch}",
            )
            continue
        update_go_version_in_mod_file(
            str(path), current_version, f"{new_major_minor}"
        )


def get_registry_token(repository: str) -> str:
    response = requests.get(
        DOCKER_AUTH_URL,
        params={
            "service": DOCKER_AUTH_SERVICE,
            "scope": f"repository:{repository}:pull",
        },
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["token"]


@lru_cache(maxsize=None)
def get_golang_image_digest(tag: str) -> str:
    """Return the digest that `golang:<tag>` currently resolves to.

    Docker resolves a `tag@digest` reference by digest and ignores the tag, so a
    stale pin silently keeps the old image around after a version bump.
    """
    url = f"{DOCKER_REGISTRY_URL}/v2/{GOLANG_IMAGE_REPOSITORY}/manifests/{tag}"
    try:
        token = get_registry_token(GOLANG_IMAGE_REPOSITORY)
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": MANIFEST_ACCEPT,
        }
        response = requests.head(
            url,
            headers=headers,
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
        )
        if response.status_code == 404:
            raise DigestResolutionError(
                f"golang:{tag} does not exist in the registry (yet)"
            )
        response.raise_for_status()
        digest = response.headers.get("Docker-Content-Digest", "")
        if not DIGEST_PATTERN.fullmatch(digest):
            # Some proxies strip or mangle the header. The digest is the hash
            # of the raw manifest bytes, so fetch and compute it.
            response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            digest = "sha256:" + hashlib.sha256(response.content).hexdigest()
            media_type = response.headers.get("Content-Type", "")
            media_type = media_type.split(";")[0].strip()
            if media_type not in MANIFEST_MEDIA_TYPES:
                # A proxy or mirror that answers with a login or error page
                # would otherwise be hashed into a valid looking but
                # meaningless pin.
                raise DigestResolutionError(
                    f"golang:{tag} returned "
                    f"'{media_type or 'no media type'}' instead of a manifest"
                )
    except requests.RequestException as e:
        raise DigestResolutionError(
            f"could not resolve the digest of golang:{tag}: {e}"
        ) from e
    logging.debug(f"golang:{tag} resolves to {digest}")
    return digest


def update_dockerfile_version_in_directory(
    new_major: str, new_minor: str, new_patch: str
):
    # Render every Dockerfile before writing any of them, so that an
    # unresolvable digest leaves the whole repository untouched instead of
    # producing a half updated one.
    rendered: Dict[str, Tuple[str, List[str]]] = {}
    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            if file == DOCKERFILE:
                dockerfile_path = os.path.join(root, file)
                update = render_dockerfile_update(
                    dockerfile_path,
                    new_major,
                    new_minor,
                    new_patch,
                )
                if update is not None:
                    rendered[dockerfile_path] = update

    for dockerfile_path, (content, bumps) in rendered.items():
        with open(dockerfile_path, "w") as dockerfile:
            dockerfile.write(content)
        # Only announce a bump once it is on disk: action.yml greps these lines
        # to build the commit message and the pull request title.
        for bump in bumps:
            logging.info(bump)
        logging.info(
            f"Updated {dockerfile_path} to version "
            f"{new_major}.{new_minor}.{new_patch}"
        )


def render_dockerfile_update(
    dockerfile_path: str, new_major: str, new_minor: str, new_patch: str
) -> Optional[Tuple[str, List[str]]]:
    """Return the new content of a Dockerfile and the bumps it contains.

    Returns None when nothing changes. Nothing is written here, so that an
    unresolvable digest can abort the run before any file is touched.
    """
    with open(dockerfile_path, "r") as file:
        lines = file.readlines()

    updated_lines = []
    bumps: List[str] = []
    for line in lines:
        match = FROM_GOLANG_PATTERN.search(line)
        if not match:
            updated_lines.append(line)
            continue

        version = match.group("version")
        variant = match.group("variant")
        new_version = (
            f"{new_major}.{new_minor}.{new_patch}"
            if version.count(".") == 2
            else f"{new_major}.{new_minor}"
        )
        if version == new_version:
            updated_lines.append(line)
            continue

        image = f"{match.group('prefix')}{new_version}{variant}"
        if match.group("digest"):
            image += f"@{get_golang_image_digest(f'{new_version}{variant}')}"
        updated_lines.append(
            line[: match.start()] + image + line[match.end() :]
        )
        bumps.append(f"bump golang version from {version} to {new_version}")

    return ("".join(updated_lines), bumps) if bumps else None


def main():
    configure_logging(LOGGING_LEVEL)
    latest_major, latest_minor, latest_patch = get_latest_go_version()

    try:
        update_dockerfile_version_in_directory(
            latest_major, latest_minor, latest_patch
        )
    except DigestResolutionError as e:
        logging.error(f"{e}; no files have been modified")
        sys.exit(1)

    update_go_version_in_directory(latest_major, latest_minor, latest_patch)


if __name__ == "__main__":
    main()
