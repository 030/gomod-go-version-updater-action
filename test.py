import logging
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from main import (
    DOCKERFILE,
    GO_MOD_FILE,
    get_go_version_from_mod_file,
    get_latest_go_version,
    main,
    update_go_version_in_directory,
    update_go_version_in_mod_file,
)

GO_VERSIONS_URL = "https://mocked-url.com"
TEST_NESTED_DOCKERFILE = "test/testdata/" + DOCKERFILE
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
    directory = os.path.dirname(filepath)

    if not os.path.exists(directory) and directory != "":
        os.makedirs(directory)

    with open(filepath, "w") as file:
        file.write(content)
        logging.info(f"Created {filepath} with content:\n{content}")


def setup_file_with_version_and_test(self: any, filepath: str):
    setup_file_with_version(filepath, "FROM golang:4.2.0\nsome line\n")
    main()
    self.assertEqual(
        read_version_from_file(filepath, r"FROM\sgolang:(\d+\.\d+\.?\d+?)"),
        f"{self.latest_major}.{self.latest_minor}.{self.latest_patch}",
    )


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
            ValueError, match="No Go version defined in file: .*go.mod"
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
        cleanup_files(TEST_NESTED_DOCKERFILE)

    def test_update_version_in_dockerfile_major_minor_patch(self):
        setup_file_with_version_and_test(self, DOCKERFILE)

    def test_update_version_in_nested_dockerfile_major_minor_patch(self):
        setup_file_with_version_and_test(self, TEST_NESTED_DOCKERFILE)


class TestGetGoVersionFromModFile(unittest.TestCase):
    def test_get_go_version_success_with_patch_version(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile(delete_on_close=False)
        mod_file.write(b"module example\n\ngo 1.2.3\n")
        mod_file.close()

        result = get_go_version_from_mod_file(mod_file.name)
        self.assertEqual(result, ("1.2.3", True))

    def test_get_go_version_success_without_patch_version(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile(delete_on_close=False)
        mod_file.write(b"module example\n\ngo 1.2\n")
        mod_file.close()

        result = get_go_version_from_mod_file(mod_file.name)
        self.assertEqual(result, ("1.2", False))

    def test_get_go_version_missing_file(self):
        self.assertRaises(
            FileNotFoundError, get_go_version_from_mod_file, "nonexistent_file"
        )

    def test_invalid_file_content(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile(delete_on_close=False)
        mod_file.write(b"module example\n")
        mod_file.close()

        self.assertRaises(
            ValueError, get_go_version_from_mod_file, mod_file.name
        )


class TestUpdateGoVersionInModFile(unittest.TestCase):
    def test_update_go_version_in_mod_file_with_patch(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile(delete_on_close=False)
        mod_file.write(b"module example\n\ngo 1.2.3\n")
        mod_file.close()

        # Execute the updater
        update_go_version_in_mod_file(mod_file.name, "1.2.3", "1.2.4")

        # Verify the result
        with open(mod_file.name, "r") as file:
            content = file.read()
            self.assertIn("go 1.2.4", content)

    def test_update_go_version_in_mod_file_without_patch(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile(delete_on_close=False)
        mod_file.write(b"module example\n\ngo 1.2\n")
        mod_file.close()

        # Execute the updater
        update_go_version_in_mod_file(mod_file.name, "1.2", "1.4")

        # Verify the result
        with open(mod_file.name, "r") as file:
            content = file.read()
            self.assertIn("go 1.4", content)

    def test_update_go_version_in_mod_file_missing_file(self):
        with patch("logging.info") as mock_logging:
            update_go_version_in_mod_file("nonexistent_file", "1.2", "1.4")
            mock_logging.assert_called_with("File not found: nonexistent_file")


class TestUpdateGoVersionInDirectory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(delete=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_update_go_version_in_directory(self):
        # Prepare go.mod files:
        # .
        # ├── go.mod
        # └── somewhere
        #     ├── else
        #     │   └── go.mod
        #     └── go.mod
        somewhere = os.path.join(self.temp_dir.name, "somewhere")
        somewhere_path = Path(somewhere)
        somewhere_path.mkdir(parents=False)
        else_path = Path(os.path.join(somewhere, "else"))
        else_path.mkdir(parents=False)
        mod_file1 = {
            "path": os.path.join(self.temp_dir.name, GO_MOD_FILE),
            "version": "1.2.3",
        }
        mod_file2 = {
            "path": os.path.join(somewhere_path, GO_MOD_FILE),
            "version": "1.2.3",
        }
        mod_file3 = {
            "path": os.path.join(else_path, GO_MOD_FILE),
            "version": "1.2",
        }
        for mod_file in [mod_file1, mod_file2, mod_file3]:
            with open(mod_file["path"], "w") as fp:
                fp.write(f"module example\n\ngo {mod_file['version']}\n")

        # Execute the updater
        update_go_version_in_directory("1", "2", "4", self.temp_dir.name)

        # Verify the result
        for mod_file in [mod_file1, mod_file2, mod_file3]:
            result = get_go_version_from_mod_file(mod_file["path"])
            if mod_file["version"].count(".") == 2:
                self.assertEqual(result, ("1.2.4", True))
            else:
                self.assertEqual(result, ("1.2", False))


if __name__ == "__main__":
    unittest.main()
