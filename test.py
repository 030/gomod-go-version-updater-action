import hashlib
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
    HTTP_RETRY_ATTEMPTS,
    HTTP_RETRY_BACKOFF_SECONDS,
    HTTP_RETRY_MAX_DELAY_SECONDS,
    DigestResolutionError,
    get_go_version_from_mod_file,
    get_golang_image_digest,
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
        mod_file = tempfile.NamedTemporaryFile()
        mod_file.write(b"module example\n\ngo 1.2.3\n")
        mod_file.flush()

        result = get_go_version_from_mod_file(mod_file.name)
        self.assertEqual(result, ("1.2.3", True))

    def test_get_go_version_success_without_patch_version(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile()
        mod_file.write(b"module example\n\ngo 1.2\n")
        mod_file.flush()

        result = get_go_version_from_mod_file(mod_file.name)
        self.assertEqual(result, ("1.2", False))

    def test_get_go_version_missing_file(self):
        self.assertRaises(
            FileNotFoundError, get_go_version_from_mod_file, "nonexistent_file"
        )

    def test_invalid_file_content(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile()
        mod_file.write(b"module example\n")
        mod_file.flush()

        self.assertRaises(
            ValueError, get_go_version_from_mod_file, mod_file.name
        )


class TestUpdateGoVersionInModFile(unittest.TestCase):
    def test_update_go_version_in_mod_file_with_patch(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile()
        mod_file.write(b"module example\n\ngo 1.2.3\n")
        mod_file.flush()

        # Execute the updater
        update_go_version_in_mod_file(mod_file.name, "1.2.3", "1.2.4")

        # Verify the result
        with open(mod_file.name, "r") as file:
            content = file.read()
            self.assertIn("go 1.2.4", content)

    def test_update_go_version_in_mod_file_without_patch(self):
        # Prepare go.mod file
        mod_file = tempfile.NamedTemporaryFile()
        mod_file.write(b"module example\n\ngo 1.2\n")
        mod_file.flush()

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
        self.temp_dir = tempfile.TemporaryDirectory()

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


OLD_DIGEST = "sha256:" + "3" * 64
NEW_DIGEST = "sha256:" + "4" * 64


def manifest_response(
    status_code: int, digest: str = "", retry_after: str = ""
):
    response = MagicMock(status_code=status_code)
    response.headers = {}
    if digest:
        response.headers["Docker-Content-Digest"] = digest
    if retry_after:
        response.headers["Retry-After"] = retry_after
    return response


def manifest_get_response(
    content: bytes, media_type: str = "application/vnd.oci.image.index.v1+json"
):
    response = MagicMock(status_code=200, content=content)
    response.headers = {"Content-Type": media_type}
    return response


def read_file(filepath: str) -> str:
    with open(filepath, "r") as file:
        return file.read()


class TestGetGolangImageDigest(unittest.TestCase):
    def setUp(self):
        get_golang_image_digest.cache_clear()

    @patch("requests.head")
    @patch("requests.get")
    def test_digest_from_header(self, mock_get, mock_head):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.return_value = manifest_response(200, NEW_DIGEST)

        self.assertEqual(get_golang_image_digest("1.2.4-alpine"), NEW_DIGEST)

        url = mock_head.call_args.args[0]
        self.assertTrue(url.endswith("/library/golang/manifests/1.2.4-alpine"))
        headers = mock_head.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer a-token")

    @patch("requests.head")
    @patch("requests.get")
    def test_digest_computed_when_header_is_stripped(self, mock_get, mock_head):
        manifest = b'{"manifests":[]}'
        mock_get.side_effect = [
            MagicMock(json=lambda: {"token": "a-token"}),
            manifest_get_response(manifest),
        ]
        mock_head.return_value = manifest_response(200)

        self.assertEqual(
            get_golang_image_digest("1.2.4"),
            "sha256:" + hashlib.sha256(manifest).hexdigest(),
        )

    @patch("requests.head")
    @patch("requests.get")
    def test_digest_computed_when_header_is_malformed(
        self, mock_get, mock_head
    ):
        manifest = b'{"manifests":[]}'
        mock_get.side_effect = [
            MagicMock(json=lambda: {"token": "a-token"}),
            manifest_get_response(manifest),
        ]
        mock_head.return_value = manifest_response(200, "not-a-digest")

        self.assertEqual(
            get_golang_image_digest("1.2.4"),
            "sha256:" + hashlib.sha256(manifest).hexdigest(),
        )

    @patch("requests.head")
    @patch("requests.get")
    def test_a_non_manifest_response_is_not_hashed(self, mock_get, mock_head):
        # A proxy that answers with a login or error page would otherwise be
        # turned into a valid looking but meaningless pin.
        mock_get.side_effect = [
            MagicMock(json=lambda: {"token": "a-token"}),
            manifest_get_response(b"<html>login</html>", "text/html"),
        ]
        mock_head.return_value = manifest_response(200)

        with pytest.raises(
            DigestResolutionError, match="instead of a manifest"
        ):
            get_golang_image_digest("1.2.4")

    @patch("requests.head")
    @patch("requests.get")
    def test_redirects_are_followed(self, mock_get, mock_head):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.return_value = manifest_response(200, NEW_DIGEST)

        get_golang_image_digest("1.2.4")

        self.assertTrue(mock_head.call_args.kwargs["allow_redirects"])

    @patch("requests.head")
    @patch("requests.get")
    def test_unpublished_tag(self, mock_get, mock_head):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.return_value = manifest_response(404)

        with pytest.raises(DigestResolutionError, match="does not exist"):
            get_golang_image_digest("1.2.4-alpine")

    @patch("time.sleep")
    @patch("requests.get")
    def test_registry_error(self, mock_get, _mock_sleep):
        mock_get.side_effect = requests.exceptions.RequestException("boom")

        with pytest.raises(DigestResolutionError, match="could not resolve"):
            get_golang_image_digest("1.2.4-alpine")

    @patch("requests.head")
    @patch("requests.get")
    def test_digest_is_resolved_once_per_tag(self, mock_get, mock_head):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.return_value = manifest_response(200, NEW_DIGEST)

        get_golang_image_digest("1.2.4-alpine")
        get_golang_image_digest("1.2.4-alpine")

        mock_head.assert_called_once()


class TestDigestLookupRetries(unittest.TestCase):
    """A blip on Docker Hub must not cost the whole run, including `go.mod`."""

    def setUp(self):
        get_golang_image_digest.cache_clear()

    @patch("time.sleep")
    @patch("requests.head")
    @patch("requests.get")
    def test_a_rate_limited_request_is_retried(
        self, mock_get, mock_head, _mock_sleep
    ):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.side_effect = [
            manifest_response(429),
            manifest_response(200, NEW_DIGEST),
        ]

        self.assertEqual(get_golang_image_digest("1.2.4-alpine"), NEW_DIGEST)

        self.assertEqual(mock_head.call_count, 2)

    @patch("time.sleep")
    @patch("requests.head")
    @patch("requests.get")
    def test_a_dropped_connection_is_retried(
        self, mock_get, mock_head, _mock_sleep
    ):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.side_effect = [
            requests.exceptions.ConnectionError("reset by peer"),
            manifest_response(200, NEW_DIGEST),
        ]

        self.assertEqual(get_golang_image_digest("1.2.4-alpine"), NEW_DIGEST)

        self.assertEqual(mock_head.call_count, 2)

    @patch("time.sleep")
    @patch("requests.head")
    @patch("requests.get")
    def test_a_persistent_registry_error_gives_up(
        self, mock_get, mock_head, _mock_sleep
    ):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        unavailable = manifest_response(503)
        unavailable.raise_for_status.side_effect = (
            requests.exceptions.HTTPError("503")
        )
        mock_head.return_value = unavailable

        with pytest.raises(DigestResolutionError, match="could not resolve"):
            get_golang_image_digest("1.2.4-alpine")

        self.assertEqual(mock_head.call_count, HTTP_RETRY_ATTEMPTS)

    @patch("time.sleep")
    @patch("requests.head")
    @patch("requests.get")
    def test_an_unpublished_tag_is_not_retried(
        self, mock_get, mock_head, mock_sleep
    ):
        # A 404 means the image is not there, not that it might be next time.
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.return_value = manifest_response(404)

        with pytest.raises(DigestResolutionError, match="does not exist"):
            get_golang_image_digest("1.2.4-alpine")

        mock_head.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("requests.head")
    @patch("requests.get")
    def test_retry_after_is_honoured(self, mock_get, mock_head, mock_sleep):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.side_effect = [
            manifest_response(429, retry_after="7"),
            manifest_response(200, NEW_DIGEST),
        ]

        get_golang_image_digest("1.2.4-alpine")

        mock_sleep.assert_called_once_with(7.0)

    @patch("time.sleep")
    @patch("requests.head")
    @patch("requests.get")
    def test_an_absurd_retry_after_is_capped(
        self, mock_get, mock_head, mock_sleep
    ):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.side_effect = [
            manifest_response(429, retry_after="86400"),
            manifest_response(200, NEW_DIGEST),
        ]

        get_golang_image_digest("1.2.4-alpine")

        mock_sleep.assert_called_once_with(HTTP_RETRY_MAX_DELAY_SECONDS)

    @patch("time.sleep")
    @patch("requests.head")
    @patch("requests.get")
    def test_a_retry_after_date_falls_back_to_the_backoff(
        self, mock_get, mock_head, mock_sleep
    ):
        mock_get.return_value = MagicMock(json=lambda: {"token": "a-token"})
        mock_head.side_effect = [
            manifest_response(429, retry_after="Wed, 21 Oct 2026 07:28:00 GMT"),
            manifest_response(200, NEW_DIGEST),
        ]

        get_golang_image_digest("1.2.4-alpine")

        mock_sleep.assert_called_once_with(float(HTTP_RETRY_BACKOFF_SECONDS))

    @patch("time.sleep")
    @patch("requests.head")
    @patch("requests.get")
    def test_a_rate_limited_token_request_is_retried(
        self, mock_get, mock_head, _mock_sleep
    ):
        mock_get.side_effect = [
            manifest_response(429),
            MagicMock(status_code=200, json=lambda: {"token": "a-token"}),
        ]
        mock_head.return_value = manifest_response(200, NEW_DIGEST)

        self.assertEqual(get_golang_image_digest("1.2.4-alpine"), NEW_DIGEST)

        self.assertEqual(mock_get.call_count, 2)


class TestUpdateDigestPinnedDockerfile(unittest.TestCase):
    latest_major, latest_minor, latest_patch = get_latest_go_version()

    def setUp(self):
        get_golang_image_digest.cache_clear()

    def tearDown(self):
        cleanup_files(DOCKERFILE, GO_MOD_FILE)

    @property
    def latest(self) -> str:
        return f"{self.latest_major}.{self.latest_minor}.{self.latest_patch}"

    @patch("requests.head")
    @patch("main.get_registry_token", return_value="a-token")
    def test_tag_and_digest_are_bumped(self, _mock_token, mock_head):
        mock_head.return_value = manifest_response(200, NEW_DIGEST)
        setup_file_with_version(
            DOCKERFILE,
            f"FROM golang:1.2.3-alpine@{OLD_DIGEST} AS builder\n",
        )

        main()

        self.assertEqual(
            read_file(DOCKERFILE),
            f"FROM golang:{self.latest}-alpine@{NEW_DIGEST} AS builder\n",
        )
        self.assertTrue(
            mock_head.call_args.args[0].endswith(f"{self.latest}-alpine")
        )

    @patch("requests.head")
    @patch("main.get_registry_token", return_value="a-token")
    def test_up_to_date_line_is_not_resolved(self, _mock_token, mock_head):
        content = f"FROM golang:{self.latest}-alpine@{OLD_DIGEST}\n"
        setup_file_with_version(DOCKERFILE, content)

        main()

        self.assertEqual(read_file(DOCKERFILE), content)
        mock_head.assert_not_called()

    @patch("requests.head")
    @patch("main.get_registry_token", return_value="a-token")
    def test_nothing_is_written_when_the_digest_is_unresolvable(
        self, _mock_token, mock_head
    ):
        mock_head.return_value = manifest_response(404)
        dockerfile = f"FROM golang:1.2.3-alpine@{OLD_DIGEST}\n"
        go_mod = "module example\n\ngo 1.2.3\n"
        setup_file_with_version(DOCKERFILE, dockerfile)
        setup_file_with_version(GO_MOD_FILE, go_mod)

        with self.assertLogs(level="INFO") as logs:
            with pytest.raises(SystemExit):
                main()

        self.assertEqual(read_file(DOCKERFILE), dockerfile)
        self.assertEqual(read_file(GO_MOD_FILE), go_mod)
        # action.yml greps for this line to build the commit message.
        self.assertFalse(
            any("bump golang version" in line for line in logs.output)
        )

    def test_major_minor_tag_keeps_its_format(self):
        setup_file_with_version(DOCKERFILE, "FROM golang:1.2-alpine\n")

        main()

        self.assertEqual(
            read_file(DOCKERFILE),
            f"FROM golang:{self.latest_major}.{self.latest_minor}-alpine\n",
        )

    def test_platform_flag_is_supported(self):
        setup_file_with_version(
            DOCKERFILE,
            "FROM --platform=$BUILDPLATFORM golang:1.2.3 AS builder\n",
        )

        main()

        self.assertEqual(
            read_file(DOCKERFILE),
            f"FROM --platform=$BUILDPLATFORM golang:{self.latest} AS builder\n",
        )


if __name__ == "__main__":
    unittest.main()
