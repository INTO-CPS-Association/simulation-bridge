"""Unit tests for simulation_bridge.src.utils.template module."""

from unittest import mock
import pytest
import simulation_bridge.src.utils.template as template_module


@pytest.fixture
def dummy_path(tmp_path):
    """Provide a dummy filesystem path for tests."""
    return tmp_path / "dummy_file"


@pytest.fixture
def mock_copy_resource_fixture():
    """Mock copy_resource function to control its behavior."""
    with mock.patch("simulation_bridge.src.utils.template.copy_resource") as m:
        yield m


@pytest.fixture
def mock_print_fixture(monkeypatch):
    """Capture print calls to verify output."""
    mock_print_obj = mock.Mock()
    monkeypatch.setattr("builtins.print", mock_print_obj)
    return mock_print_obj


class TestCreateDirectory:  # pylint: disable=too-few-public-methods
    """Test cases for create_directory function."""

    def test_create_directory_created_and_skipped_and_error(self, monkeypatch,
                                                          mock_print_fixture): # pylint: disable=W0621
        """Test create_directory status for existing, created and error cases."""
        mock_print_fixture.reset_mock()

        # Existing directory triggers 'skipped'
        monkeypatch.setattr("os.path.exists", lambda path: True)
        status, error = template_module.create_directory("dir", "anypath")
        assert status == "skipped"
        assert error is None
        mock_print_fixture.assert_called_once()

        mock_print_fixture.reset_mock()

        # Successful creation triggers 'created'
        monkeypatch.setattr("os.path.exists", lambda path: False)
        monkeypatch.setattr("os.makedirs", lambda path, exist_ok: None)
        status, error = template_module.create_directory("dir", "anypath")
        assert status == "created"
        assert error is None

        # OSError triggers 'error'
        def raise_oserror(*args, **kwargs):
            raise OSError("fail")

        monkeypatch.setattr("os.makedirs", raise_oserror)
        status, error = template_module.create_directory("dir", "anypath")
        assert status == "error"
        assert "fail" in error


class TestCreateFile:  # pylint: disable=too-few-public-methods
    """Test cases for create_file function."""

    def test_create_file_skipped_created_error(self, monkeypatch, tmp_path,
                                             mock_copy_resource_fixture, mock_print_fixture): # pylint: disable=W0621
        """Test create_file for 'skipped', 'created' and 'error' outcomes.""" 
        full_path = tmp_path / "file.txt"
        mock_print_fixture.reset_mock()
        mock_copy_resource_fixture.reset_mock()

        # File exists -> skipped
        monkeypatch.setattr("os.path.exists", lambda path: True)
        status, error = template_module.create_file(
            "file.txt", str(full_path), "pkg", "res"
        )
        assert status == "skipped"
        assert error is None

        # File does not exist, parent dir created, copy_resource succeeds
        monkeypatch.setattr("os.path.exists", lambda path: False)
        monkeypatch.setattr("os.makedirs", lambda path, exist_ok: None)
        mock_copy_resource_fixture.return_value = True
        status, error = template_module.create_file(
            "file.txt", str(full_path), "pkg", "res"
        )
        assert status == "created"
        assert error is None
        mock_copy_resource_fixture.assert_called_once_with("pkg", "res", str(full_path))

        # copy_resource fails
        mock_copy_resource_fixture.reset_mock()
        mock_copy_resource_fixture.return_value = False
        status, error = template_module.create_file(
            "file.txt", str(full_path), "pkg", "res"
        )
        assert status == "error"
        assert "Failed to create" in error

        # makedirs raises OSError
        monkeypatch.setattr("os.path.exists", lambda path: False)
        monkeypatch.setattr("os.makedirs", mock.Mock(side_effect=OSError("fail")))
        status, error = template_module.create_file(
            "path/file.txt", "path/file.txt", "pkg", "res"
        )
        assert status == "error"
        assert "Failed to create parent directory" in error


def test_print_summary_outputs(mock_print_fixture): # pylint: disable=W0621
    """Test print_summary outputs the expected summary."""
    created = ["file1", "file2"]
    skipped = ["file3"]
    errors = ["error1"]
    descriptions = {"file1": "desc1", "file2": "desc2", "file3": "desc3"}

    template_module.print_summary(created, skipped, errors, descriptions)
    assert mock_print_fixture.call_count > 5
    mock_print_fixture.assert_any_call("Project generation summary:")


class TestFileFunctions:  # pylint: disable=too-few-public-methods
    """Test cases for file-related utility functions."""

    def test_get_files_to_generate_and_descriptions(self):
        """Test get_files_to_generate and get_file_descriptions return dicts."""
        files = template_module.get_files_to_generate()
        desc = template_module.get_file_descriptions()
        assert isinstance(files, dict)
        assert isinstance(desc, dict)
        assert "client/simulation.yaml" in files
        assert "client/simulation.yaml" in desc


class TestGenerateDefaultConfig:  # pylint: disable=too-few-public-methods
    """Test cases for generate_default_config function."""

    def test_generate_default_config_existing_file(self, monkeypatch, mock_print_fixture): # pylint: disable=W0621
        """Test generate_default_config does nothing if config file exists."""
        monkeypatch.setattr("os.path.exists", lambda path: True)
        template_module.generate_default_config()
        mock_print_fixture.assert_any_call(mock.ANY)  # prints file exists message

    def test_generate_default_config_copy_and_errors(self, monkeypatch, mock_print_fixture): # pylint: disable=W0621
        """Test generate_default_config copies config or prints errors."""
        mock_print_fixture.reset_mock()

        # File doesn't exist, copy succeeds
        monkeypatch.setattr("os.path.exists", lambda path: False)
        monkeypatch.setattr(template_module, "copy_config_template", lambda path: None)
        template_module.generate_default_config()
        mock_print_fixture.assert_any_call(mock.ANY)  # prints success message

        mock_print_fixture.reset_mock()

        # File doesn't exist, copy raises FileNotFoundError
        def raise_fnfe(path):
            raise FileNotFoundError()

        monkeypatch.setattr(template_module, "copy_config_template", raise_fnfe)
        template_module.generate_default_config()
        mock_print_fixture.assert_any_call("Error: Template configuration file not found.")

        mock_print_fixture.reset_mock()

        # File doesn't exist, copy raises OSError
        def raise_oserror(path):
            raise OSError("fail")

        monkeypatch.setattr(template_module, "copy_config_template", raise_oserror)
        template_module.generate_default_config()
        mock_print_fixture.assert_any_call(mock.ANY)  # prints error message


class TestGenerateDefaultProject:  # pylint: disable=too-few-public-methods
    """Test cases for generate_default_project function."""

    def test_generate_default_project_flow(self, monkeypatch, mock_print_fixture): # pylint: disable=W0621
        """Test generate_default_project runs flow with create_file/directory."""
        monkeypatch.setattr(template_module, "get_files_to_generate", lambda: {
            "dir/": ("pkg", "res"),
            "file.txt": ("pkg", "res"),
        })
        monkeypatch.setattr(template_module, "get_file_descriptions", lambda: {
            "dir/": "desc dir",
            "file.txt": "desc file",
        })
        monkeypatch.setattr("os.path.join", lambda *args: "/".join(args))

        statuses = iter([
            ("created", None),  # dir created
            ("skipped", None),  # file skipped
        ])

        def fake_create_directory(fp, full):  # pylint: disable=unused-argument
            return next(statuses)

        def fake_create_file(fp, full, pkg, res):  # pylint: disable=unused-argument
            return next(statuses)

        monkeypatch.setattr(template_module, "create_directory", fake_create_directory)
        monkeypatch.setattr(template_module, "create_file", fake_create_file)

        template_module.generate_default_project()
        assert mock_print_fixture.call_count > 5
