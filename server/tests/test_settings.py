import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.settings import PROJECT_DIRECTORY, data_directory
from server.storage import Store


class SettingsTests(unittest.TestCase):
    def test_default_directory_is_inside_the_checkout(self):
        with patch.dict(os.environ, {"TCC_DATA_DIR": ""}):
            self.assertEqual(data_directory(), PROJECT_DIRECTORY / ".tcc-data")

    def test_default_does_not_depend_on_terminal_directory(self):
        with patch.dict(os.environ, {"TCC_DATA_DIR": ""}), patch("pathlib.Path.cwd", return_value=Path("/workspaces/another-folder")):
            self.assertEqual(data_directory(), PROJECT_DIRECTORY / ".tcc-data")

    def test_explicit_directory_is_preserved_and_writable(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"TCC_DATA_DIR": folder}):
            self.assertEqual(data_directory(), Path(folder))
            database = Store()
            self.assertEqual(database.directory, Path(folder))
            self.assertTrue(database.path.is_file())
