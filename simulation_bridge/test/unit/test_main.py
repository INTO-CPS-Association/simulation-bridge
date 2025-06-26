"""
Unit tests for the main module of the simulation bridge.
Tests the command line interface and main functionality.
"""

from unittest import mock
import pytest

import simulation_bridge.src.main as main_module


@pytest.fixture
def mock_config_file(tmp_path):
    """Create a temporary config file for testing."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("logging:\n  level: INFO\n  file: log.txt")
    return str(config_path)


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return mock.Mock()


@pytest.fixture
def mock_config_data():
    """Create mock configuration data for testing."""
    return {
        "logging": {"level": "INFO", "file": "log.txt"}
    }


def test_generate_config_flag(monkeypatch):
    """Test the --generate-config flag functionality."""
    generate_mock = mock.Mock()
    monkeypatch.setattr(main_module, "generate_default_config", generate_mock)

    main_module.main.main(
        ["--generate-config"], standalone_mode=False
    )  # click command simulates entrypoint

    generate_mock.assert_called_once()


def test_generate_project_flag(monkeypatch):
    """Test the --generate-project flag functionality."""
    generate_mock = mock.Mock()
    monkeypatch.setattr(main_module, "generate_default_project", generate_mock)

    main_module.main.main(
        ["--generate-project"], standalone_mode=False
    )

    generate_mock.assert_called_once()


def test_main_with_config_file(monkeypatch, mock_config_file):  # pylint: disable=redefined-outer-name
    """Test main function with a specific config file."""
    run_mock = mock.Mock()
    monkeypatch.setattr(main_module, "run_bridge", run_mock)

    main_module.main.main(
        ["--config-file", mock_config_file], standalone_mode=False)

    run_mock.assert_called_once_with(mock_config_file)


def test_main_no_config_prints(monkeypatch):
    """Test main function behavior when no config file is found."""
    monkeypatch.setattr(main_module.os.path, "exists", lambda _: False)

    print_mock = mock.Mock()
    monkeypatch.setattr("builtins.print", print_mock)

    main_module.main.main([], standalone_mode=False)

    # Flatten all print args and join them into one string for assertion
    printed_output = " ".join(
        str(arg)
        for call in print_mock.call_args_list
        for arg in call.args
    )

    assert "Configuration file config.yaml not found." in printed_output


def test_main_fallback_config(monkeypatch, tmp_path):
    """Test main function with fallback to default config."""
    default_config_path = tmp_path / "config.yaml"
    default_config_path.write_text("logging:\n  level: INFO\n  file: log.txt")

    monkeypatch.setattr(main_module.os.path, "exists", lambda _: True)
    monkeypatch.setattr(
        main_module,
        "CONFIG_FILENAME",
        str(default_config_path))

    run_mock = mock.Mock()
    monkeypatch.setattr(main_module, "run_bridge", run_mock)

    main_module.main.main([], standalone_mode=False)

    run_mock.assert_called_once_with(str(default_config_path))


def test_run_bridge_success(monkeypatch, mock_config_file, mock_config_data, mock_logger):  # pylint: disable=redefined-outer-name
    """Test successful bridge execution."""
    mock_bridge = mock.Mock()

    monkeypatch.setattr(main_module, "load_config", lambda _: mock_config_data)
    monkeypatch.setattr(
        main_module,
        "setup_logger",
        lambda **kwargs: mock_logger)
    monkeypatch.setattr(
        main_module,
        "BridgeOrchestrator",
        lambda config_path: mock_bridge)

    main_module.run_bridge(mock_config_file)

    mock_logger.debug.assert_called_once()
    mock_bridge.start.assert_called_once()


def test_run_bridge_keyboard_interrupt(monkeypatch, mock_config_file, mock_config_data, mock_logger):  # pylint: disable=redefined-outer-name,line-too-long
    """Test bridge execution with keyboard interrupt."""
    mock_bridge = mock.Mock()
    mock_bridge.start.side_effect = KeyboardInterrupt

    monkeypatch.setattr(main_module, "load_config", lambda _: mock_config_data)
    monkeypatch.setattr(
        main_module,
        "setup_logger",
        lambda **kwargs: mock_logger)
    monkeypatch.setattr(
        main_module,
        "BridgeOrchestrator",
        lambda config_path: mock_bridge)

    main_module.run_bridge(mock_config_file)

    mock_logger.info.assert_called_with("Stopping application via interrupt")
    mock_bridge.stop.assert_called_once()


def test_run_bridge_os_error(monkeypatch, mock_config_file, mock_config_data, mock_logger):  # pylint: disable=redefined-outer-name
    """Test bridge execution with OS error."""
    mock_bridge = mock.Mock()
    mock_bridge.start.side_effect = OSError("disk full")

    monkeypatch.setattr(main_module, "load_config", lambda _: mock_config_data)
    monkeypatch.setattr(
        main_module,
        "setup_logger",
        lambda **kwargs: mock_logger)
    monkeypatch.setattr(
        main_module,
        "BridgeOrchestrator",
        lambda config_path: mock_bridge)

    main_module.run_bridge(mock_config_file)

    mock_logger.error.assert_called_with(
        "OS error: %s", "disk full", exc_info=True)
    mock_bridge.stop.assert_called_once()


def test_run_bridge_value_error(monkeypatch, mock_config_file, mock_config_data, mock_logger):  # pylint: disable=redefined-outer-name
    """Test bridge execution with value error."""
    mock_bridge = mock.Mock()
    mock_bridge.start.side_effect = ValueError("invalid format")

    monkeypatch.setattr(main_module, "load_config", lambda _: mock_config_data)
    monkeypatch.setattr(
        main_module,
        "setup_logger",
        lambda **kwargs: mock_logger)
    monkeypatch.setattr(
        main_module,
        "BridgeOrchestrator",
        lambda config_path: mock_bridge)

    main_module.run_bridge(mock_config_file)

    mock_logger.error.assert_called_with(
        "Configuration error: %s",
        "invalid format",
        exc_info=True)
    mock_bridge.stop.assert_called_once()
