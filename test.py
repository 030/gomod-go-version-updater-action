import logging
import os
import pytest
import re
import unittest
from main import get_latest_go_version, main, GO_MOD_FILE


def get_golang_version_from_go_mod_file() -> str:
    try:
        with open(GO_MOD_FILE, 'r') as file:
            file_content = file.read()
            print(f"Content of the file:\n{file_content}")
            pattern = r'\d+\.\d+\.?\d+?'
            matches = re.findall(pattern, file_content)
            print("Extracted values:", matches[0])
            return matches[0]
    except FileNotFoundError:
        print(f"File not found: {GO_MOD_FILE}")
    except Exception as e:
        print(f"An error occurred: {e}")


def setup_helper_create_go_mod_with_a_golang_version(version: str):
    with open(GO_MOD_FILE, "w") as file:
        file.write("module github.com/030/gomod-go-version-updater-action\n\n")
        file.write("go "+version+"\n\n")
        file.write("require (\n")
        file.write("github.com/go-openapi/errors v0.21.1\n")
        file.write("github.com/aws/aws-sdk-go v1.50.30\n")
        file.write(")")


def cleanup_helper():
    exception_occurred = False
    try:
        if os.path.exists(GO_MOD_FILE):
            os.remove(GO_MOD_FILE)
            print(f"The file '{GO_MOD_FILE}' has been successfully removed.")
    except Exception as e:
        pytest.fail(f"An error occurred while trying to remove the file: {e}")


class TestUpdateGolangVersionInGoModFile(unittest.TestCase):
    latest_major, latest_minor, latest_patch = get_latest_go_version()

    def tearDown(self):
        cleanup_helper()

    def test_update_golang_version_consisting_of_major_minor_and_patch(self):
        setup_helper_create_go_mod_with_a_golang_version("1.2.3")
        main()
        self.assertEqual(get_golang_version_from_go_mod_file(), TestUpdateGolangVersionInGoModFile.latest_major+"." +
                         TestUpdateGolangVersionInGoModFile.latest_minor+"."+TestUpdateGolangVersionInGoModFile.latest_patch)

    def test_update_golang_version_consisting_of_major_and_minor(self):
        setup_helper_create_go_mod_with_a_golang_version("4.2")
        main()
        self.assertEqual(get_golang_version_from_go_mod_file(), TestUpdateGolangVersionInGoModFile.latest_major +
                         "."+TestUpdateGolangVersionInGoModFile.latest_minor)

    def test_update_golang_version_consisting_of_major(self):
        setup_helper_create_go_mod_with_a_golang_version("42")
        with pytest.raises(ValueError, match="no golang version defined in file: go.mod"):
            main()

    def test_update_golang_version_if_go_mod_does_not_exist(self):
        with pytest.raises(ValueError, match="file not found: go.mod"):
            main()


if __name__ == '__main__':
    unittest.main()
