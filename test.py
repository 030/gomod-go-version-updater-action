import os
import re
import unittest
from main import (
    DOCKERFILE,
    GO_MOD_FILE,
    get_latest_go_version,
    main,
)
from unittest.mock import mock_open, patch, MagicMock
import logging
import requests
import pytest

GO_VERSIONS_URL = "https://mocked-url.com"
logging.basicConfig(level=logging.INFO)


def read_version_from_file(filepath: str, pattern: str) -> str:
    try:
        with open(filepath, "r") as file:
            matches = re.findall(pattern, file.read())
            if matches:
                logging.info(f"Extracted version: {matches[0]} from {filepath}")
                return matches[0]
    except FileNotFoundError:
        logging.error(f"File not found: {filepath}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")


def setup_file_with_version(filepath: str, content: str):
    with open(filepath, "w") as file:
        file.write(content)
        logging.info(f"Created {filepath} with content:\n{content}")


def cleanup_files(*filepaths):
    for filepath in filepaths:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logging.info(f"Removed file: {filepath}")
        except Exception as e:
            pytest.fail(f"Error removing file {filepath}: {e}")


class TestUpdateGolangVersionInGoModFile(unittest.TestCase):
    latest_major, latest_minor, latest_patch = get_latest_go_version()

    def tearDown(self):
        cleanup_files(GO_MOD_FILE)

    def test_update_golang_version_major_minor_patch(self):
        setup_file_with_version(
            GO_MOD_FILE,
            "module github.com/030/gomod-go-version-updater-action\n\ngo 1.2.3\n",
        )
        main()
        self.assertEqual(
            read_version_from_file(GO_MOD_FILE, r"\d+\.\d+\.?\d+?"),
            f"{self.latest_major}.{self.latest_minor}.{self.latest_patch}",
        )

    def test_update_golang_version_major_minor(self):
        setup_file_with_version(
            GO_MOD_FILE,
            "module github.com/030/gomod-go-version-updater-action\n\ngo 4.2\n",
        )
        main()
        self.assertEqual(
            read_version_from_file(GO_MOD_FILE, r"\d+\.\d+\.?\d+?"),
            f"{self.latest_major}.{self.latest_minor}",
        )

    def test_update_golang_version_major(self):
        setup_file_with_version(GO_MOD_FILE, "module example\n\ngo 42\n")
        with pytest.raises(
            ValueError, match="No Go version defined in file: go.mod"
        ):
            main()


class TestGetLatestGoVersion(unittest.TestCase):
    @patch("requests.get")
    def test_successful_fetch(self, mock_get):
        mock_get.return_value = MagicMock(
            json=lambda: [{"version": "go1.18.3"}], status_code=200
        )
        major, minor, patch = get_latest_go_version()
        self.assertEqual((major, minor, patch), ("1", "18", "3"))

    @patch("requests.get")
    def test_non_matching_version_format(self, mock_get):
        mock_get.return_value = MagicMock(
            json=lambda: [{"version": "invalid_version"}], status_code=200
        )
        self.assertEqual(get_latest_go_version(), ("", "", ""))

    @patch("requests.get")
    def test_http_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )
        with self.assertRaises(SystemExit):
            get_latest_go_version()


class TestUpdateGolangVersionInDockerfile(unittest.TestCase):
    latest_major, latest_minor, latest_patch = get_latest_go_version()

    def tearDown(self):
        cleanup_files(DOCKERFILE)

    def test_update_version_in_dockerfile_major_minor_patch(self):
        setup_file_with_version(DOCKERFILE, "FROM golang:4.2.0\nsome line\n")
        main()
        self.assertEqual(
            read_version_from_file(
                DOCKERFILE, r"FROM\sgolang:(\d+\.\d+\.?\d+?)"
            ),
            f"{self.latest_major}.{self.latest_minor}.{self.latest_patch}",
        )


if __name__ == "__main__":
    unittest.main()
