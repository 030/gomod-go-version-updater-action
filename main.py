import logging
import os
import re
import requests
import sys


GO_MOD_FILE = "go.mod"
GO_MOD_GO_VERSION_REGEX = "go\s\d+.*"
GO_VERSIONS_URL = 'https://go.dev/dl/?mode=json'


def determine_whether_go_version_in_go_mod_file_contains_patch_version() -> (str, bool):
    patch = False
    version = ""
    try:
        with open(GO_MOD_FILE, 'r') as file:
            major, minor, patch = "", "", ""
            content = file.read()
            go_version = re.search(r'go\s(\d+)\.(\d+)\.?(\d+)?', content)
            if go_version:
                major = go_version.group(1)
                logging.debug(f"major found in go.mod: {major}")
                minor = go_version.group(2)
                logging.debug(f"minor found in go.mod: {minor}")
                patch = go_version.group(3)
                logging.debug(f"patch found in go.mod: {patch}")
            else:
                raise ValueError(f"no golang version defined in file: {GO_MOD_FILE}")
            if patch:
                version = major+"."+minor+"."+patch
                logging.debug(f"go version consists of major, minor and patch: {version}")
                patch = True
            else:
                version = major+"."+minor
                logging.debug(f"go version consists of major and minor: {version}")
    except FileNotFoundError:
        raise ValueError(f"File not found: {GO_MOD_FILE}")
    logging.debug(f"current golang version that is defined in the go.mod: {version}")
    return version, patch


def get_latest_go_version():
    major, minor, patch = "", "", ""

    try:
        response = requests.get(GO_VERSIONS_URL)
        response.raise_for_status()
        data = response.json()
        latest_version = data[0]['version']
        logging.debug(f"latest go version: {latest_version} according to: {GO_VERSIONS_URL}")
        version_regex = re.compile(r'go(\d+)\.(\d+)\.(\d+)')
        match_data = version_regex.match(latest_version)
        if match_data:
            major, minor, patch = match_data.groups()
        else:
            logging.info("No version found in the input string.")
    except requests.exceptions.RequestException as e:
        logging.info(f"Error fetching data: {GO_VERSIONS_URL} {e}")
        sys.exit(1)
    logging.debug(f"latest go major: {major}")
    logging.debug(f"latest go minor: {minor}")
    logging.debug(f"latest go patch: {patch}")

    return major, minor, patch


def regex_replace_go_version_in_go_mod_file(current_version: str, replacement: str):
    try:
        with open(GO_MOD_FILE, 'r') as file:
            content = file.read()
        modified_content = re.sub(GO_MOD_GO_VERSION_REGEX, "go "+replacement, content)
        with open(GO_MOD_FILE, 'w') as file:
            file.write(modified_content)
        logging.info(
            f"bump golang version in go.mod file from {current_version} to {replacement}")
    except FileNotFoundError:
        logging.info(f"File not found: {GO_MOD_FILE}")
    except Exception as e:
        logging.info(f"An error occurred: {e}")


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    configure_logging()
    latest_major, latest_minor, latest_patch = get_latest_go_version()
    current_version, patch = determine_whether_go_version_in_go_mod_file_contains_patch_version()
    if patch:
        regex_replace_go_version_in_go_mod_file(current_version, latest_major+"."+latest_minor+"."+latest_patch)
    else:
        regex_replace_go_version_in_go_mod_file(current_version, latest_major+"."+latest_minor)


if __name__ == "__main__":
    main()
