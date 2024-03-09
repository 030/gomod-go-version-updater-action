import logging
import os
import re
import requests
import sys


GO_MOD_FILE = "go.mod"
GO_MOD_GO_VERSION_REGEX = "go .*"
GO_VERSIONS_URL = 'https://go.dev/dl/?mode=json'


def determine_whether_go_version_in_go_mod_file_contains_patch_version() -> bool:
    patch = False

    try:
        with open(GO_MOD_FILE, 'r') as file:
            major, minor, patch = "", "", ""

            content = file.read()
            go_version = re.search(r'go\s(\d+)\.(\d+)\.?(\d+)?', content)
            if go_version:
                major = go_version.group(1)
                logging.info(major)
                minor = go_version.group(2)
                logging.info(minor)
                patch = go_version.group(3)
                logging.info(patch)
            else:
                raise ValueError(f"no golang version defined in file: {GO_MOD_FILE}")

            go_mod_file_path = GO_MOD_FILE
            latest_major, latest_minor, latest_patch = get_latest_go_version()

            if patch:
                logging.info(f"go version consists of major, minor and patch: {major}.{minor}.{patch}")
                patch = True
            else:
                logging.info(f"go version consists of major and minor: {major}.{minor}")
    except FileNotFoundError:
        raise ValueError(f"File not found: {GO_MOD_FILE}")

    return patch


def get_latest_go_version():
    major, minor, patch = "", "", ""

    try:
        response = requests.get(GO_VERSIONS_URL)
        response.raise_for_status()

        data = response.json()
        latest_version = data[0]['version']
        logging.info(latest_version)

        version_regex = re.compile(r'go(\d+)\.(\d+)\.(\d+)')
        match_data = version_regex.match(latest_version)

        if match_data:
            major, minor, patch = match_data.groups()
        else:
            logging.info("No version found in the input string.")
    except requests.exceptions.RequestException as e:
        logging.info(f"Error fetching data: {GO_VERSIONS_URL} {e}")
        sys.exit(1)

    logging.info(f"Latest Go Version: {major}.{minor}.{patch}")

    return major, minor, patch


def regex_replace_go_version_in_go_mod_file(replacement):
    try:
        # Read the content of the file
        with open(GO_MOD_FILE, 'r') as file:
            content = file.read()

        # Use re.sub to replace the pattern with the replacement
        modified_content = re.sub(GO_MOD_GO_VERSION_REGEX, "go "+replacement, content)

        # Write the modified content back to the file
        with open(GO_MOD_FILE, 'w') as file:
            file.write(modified_content)

        logging.info(f"Pattern '{GO_MOD_GO_VERSION_REGEX}' replaced with '{replacement}' in '{GO_MOD_FILE}'.")
    except FileNotFoundError:
        logging.info(f"File not found: {GO_MOD_FILE}")
    except Exception as e:
        logging.info(f"An error occurred: {e}")


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    configure_logging()

    latest_major, latest_minor, latest_patch = get_latest_go_version()

    if determine_whether_go_version_in_go_mod_file_contains_patch_version():
        regex_replace_go_version_in_go_mod_file(latest_major+"."+latest_minor+"."+latest_patch)
    else:
        regex_replace_go_version_in_go_mod_file(latest_major+"."+latest_minor)


if __name__ == "__main__":
    main()
