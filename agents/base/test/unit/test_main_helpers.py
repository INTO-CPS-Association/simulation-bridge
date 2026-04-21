"""Tests for shared main/CLI helper utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from base_agent.comm.main_helpers import (
    copy_packaged_resource,
    generate_project_files,
    run_main_with_default_config,
)


def test_run_main_with_default_config_prioritizes_generate_config() -> None:
    """Generate-config flag should take precedence over project generation."""
    generate_config = MagicMock()
    generate_project = MagicMock()
    run_agent = MagicMock()

    run_main_with_default_config(
        config_file="custom.yaml",
        generate_config=True,
        generate_project=True,
        generate_config_func=generate_config,
        generate_project_func=generate_project,
        run_agent_func=run_agent,
        command_name="matlab-agent",
    )

    generate_config.assert_called_once()
    generate_project.assert_not_called()
    run_agent.assert_not_called()


def test_run_main_with_default_config_uses_explicit_path() -> None:
    """Explicit config path should execute run_agent directly."""
    run_agent = MagicMock()

    run_main_with_default_config(
        config_file="custom.yaml",
        generate_config=False,
        generate_project=False,
        generate_config_func=MagicMock(),
        generate_project_func=MagicMock(),
        run_agent_func=run_agent,
        command_name="matlab-agent",
    )

    run_agent.assert_called_once_with("custom.yaml")


def test_run_main_with_default_config_uses_default_path_when_present() -> None:
    """Missing explicit path should fallback to local config.yaml when it exists."""
    run_agent = MagicMock()

    with patch("pathlib.Path.exists", return_value=True):
        run_main_with_default_config(
            config_file=None,
            generate_config=False,
            generate_project=False,
            generate_config_func=MagicMock(),
            generate_project_func=MagicMock(),
            run_agent_func=run_agent,
            command_name="matlab-agent",
        )

    run_agent.assert_called_once_with("config.yaml")


def test_run_main_with_default_config_prints_help_when_missing() -> None:
    """Missing default config should print guidance and avoid run_agent call."""
    run_agent = MagicMock()

    with patch("pathlib.Path.exists", return_value=False), patch("builtins.print") as mock_print:
        run_main_with_default_config(
            config_file=None,
            generate_config=False,
            generate_project=False,
            generate_config_func=MagicMock(),
            generate_project_func=MagicMock(),
            run_agent_func=run_agent,
            command_name="matlab-agent",
        )

    run_agent.assert_not_called()
    printed_text = " ".join(str(call) for call in mock_print.call_args_list)
    assert "Configuration file 'config.yaml' not found." in printed_text
    assert "matlab-agent --generate-config" in printed_text


def test_copy_packaged_resource_importlib_path() -> None:
    """Importlib path should be used when available."""
    mock_resource = MagicMock()
    mock_resource.joinpath.return_value = Path("resource.template")

    with patch("importlib.resources.files", return_value=mock_resource), \
            patch("builtins.open", new_callable=MagicMock) as mock_open:
        src_handle = MagicMock()
        src_handle.read.return_value = b"content"
        dst_handle = MagicMock()
        mock_open.return_value.__enter__.side_effect = [src_handle, dst_handle]
        mock_open.return_value.__exit__.return_value = None

        copy_packaged_resource("pkg", "file.template", Path("output.file"))

    mock_resource.joinpath.assert_called_once_with("file.template")
    dst_handle.write.assert_called_once_with(b"content")


def test_copy_packaged_resource_pkg_resources_fallback() -> None:
    """pkg_resources fallback should be used when importlib path is unavailable."""
    mock_pkg_resources = MagicMock()
    mock_pkg_resources.resource_string.return_value = b"fallback"

    with patch("importlib.resources.files", side_effect=ImportError()), \
            patch.dict("sys.modules", {"pkg_resources": mock_pkg_resources}), \
            patch("builtins.open", new_callable=MagicMock) as mock_open:
        dst_handle = MagicMock()
        mock_open.return_value.__enter__.return_value = dst_handle
        mock_open.return_value.__exit__.return_value = None

        copy_packaged_resource("pkg", "file.template", Path("output.file"))

    mock_pkg_resources.resource_string.assert_called_once_with("pkg", "file.template")
    dst_handle.write.assert_called_once_with(b"fallback")


def test_generate_project_files_reports_created_and_existing() -> None:
    """Project file generation should split created and existing file paths."""
    files_to_generate = {
        "config.yaml": ("pkg.a", "config.yaml.template"),
        "client/use.yaml": ("pkg.b", "use.yaml.template"),
    }

    def fake_exists(path_obj: Path) -> bool:
        return str(path_obj) == "config.yaml"

    with patch("pathlib.Path.exists", new=fake_exists), \
            patch("pathlib.Path.mkdir"), \
            patch("base_agent.comm.main_helpers.copy_packaged_resource") as mock_copy:
        created_files, existing_files = generate_project_files(files_to_generate)

    assert existing_files == ["config.yaml"]
    assert created_files == ["client/use.yaml"]
    mock_copy.assert_called_once_with(
        "pkg.b",
        "use.yaml.template",
        Path("client/use.yaml"),
    )
