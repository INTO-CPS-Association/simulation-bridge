"""
Test suite for simulation_bridge.src.utils.certs module.

Uses pytest and unittest.mock for structured, isolated tests
of CertificateGenerator and ensure_certificates functionalities.
"""

import datetime
from unittest import mock
import pytest
from simulation_bridge.src.utils import certs

# pylint: disable=too-many-arguments,unused-argument,protected-access,redefined-outer-name


@pytest.fixture
def cert_generator():
    """Fixture providing a CertificateGenerator instance with default params."""
    return certs.CertificateGenerator()


@pytest.fixture
def mock_logger(monkeypatch):
    """Fixture to mock the module-level logger."""
    mock_log = mock.Mock()
    monkeypatch.setattr(certs, "logger", mock_log)
    return mock_log


class TestFilesExist:
    """Tests for CertificateGenerator.files_exist method."""

    def test_files_exist_both_present(self, monkeypatch, cert_generator):
        """Return True if both cert and key files exist."""
        monkeypatch.setattr(certs.Path, "exists", lambda self: True)
        assert cert_generator.files_exist("cert.pem", "key.pem") is True

    def test_files_exist_one_missing(self, monkeypatch, cert_generator):
        """Return False if either cert or key file is missing."""

        def exists_side_effect(self):
            return self.name == "cert.pem"

        monkeypatch.setattr(certs.Path, "exists", exists_side_effect)
        assert cert_generator.files_exist("cert.pem", "key.pem") is False


class TestValidateCertificates:
    """Tests for CertificateGenerator._validate_certificates."""

    def test_validate_certificates_valid(self, monkeypatch):
        """
        Test _validate_certificates returns True for valid cert and matching key.
        """
        cert_generator = certs.CertificateGenerator()

        mock_cert = mock.Mock()
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_cert.not_valid_before_utc = now - datetime.timedelta(days=1)
        mock_cert.not_valid_after_utc = now + datetime.timedelta(days=365)

        mock_public_key = mock.Mock()
        mock_public_key.key_size = 2048
        mock_public_key.public_numbers.return_value = mock.Mock(n=123, e=65537)
        mock_cert.public_key.return_value = mock_public_key

        mock_private_key = mock.Mock()
        mock_private_public_key = mock.Mock()
        mock_private_public_key.key_size = 2048
        mock_private_public_key.public_numbers.return_value = mock.Mock(
            n=123, e=65537)
        mock_private_key.public_key.return_value = mock_private_public_key

        monkeypatch.setattr("builtins.open", mock.mock_open(read_data=b"data"))
        monkeypatch.setattr(
            certs.x509,
            "load_pem_x509_certificate",
            lambda data: mock_cert)
        monkeypatch.setattr(
            certs.serialization, "load_pem_private_key", lambda data,
            password=None: mock_private_key
        )

        valid, msg = cert_generator._validate_certificates(
            "cert.pem", "key.pem")
        assert valid is True, f"Expected True but got False with msg: {msg}"

    def test_validate_certificates_expired(self, monkeypatch, cert_generator):
        """Return False with expiration message if cert expired."""
        mock_cert = mock.Mock()
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_cert.not_valid_after_utc = now - datetime.timedelta(days=1)
        mock_cert.not_valid_before_utc = now - datetime.timedelta(days=10)

        monkeypatch.setattr("builtins.open", mock.mock_open(read_data=b"data"))
        monkeypatch.setattr(certs.x509, "load_pem_x509_certificate",
                            lambda data: mock_cert)
        monkeypatch.setattr(certs.serialization, "load_pem_private_key",
                            lambda data, password=None: mock.Mock())

        valid, msg = cert_generator._validate_certificates(
            "cert.pem", "key.pem")
        assert valid is False
        assert "expired" in msg

    def test_validate_certificates_file_not_found(self, cert_generator):
        """Return False with file not found message if file missing."""

        def open_side_effect(*args, **kwargs):
            raise FileNotFoundError("No such file")

        with mock.patch("builtins.open", side_effect=open_side_effect):
            valid, msg = cert_generator._validate_certificates(
                "cert.pem", "key.pem")

        assert valid is False
        assert "not found" in msg

    def test_validate_certificates_key_mismatch(
            self, monkeypatch, cert_generator):
        """Return False if certificate and private key do not match."""
        now = datetime.datetime.now(datetime.timezone.utc)
        mock_cert = mock.Mock()
        mock_cert.not_valid_after_utc = now + datetime.timedelta(days=60)
        mock_cert.not_valid_before_utc = now - datetime.timedelta(days=1)

        cert_pub_key = mock.Mock(
            key_size=2048, public_numbers=mock.Mock(
                n=123, e=65537))
        priv_pub_key = mock.Mock(
            key_size=2048, public_numbers=mock.Mock(
                n=999, e=65537))

        mock_cert.public_key.return_value = cert_pub_key
        mock_private_key = mock.Mock()
        mock_private_key.public_key.return_value = priv_pub_key

        monkeypatch.setattr("builtins.open", mock.mock_open(read_data=b"data"))
        monkeypatch.setattr(
            certs.x509,
            "load_pem_x509_certificate",
            lambda data: mock_cert)
        monkeypatch.setattr(certs.serialization, "load_pem_private_key",
                            lambda data, password=None: mock_private_key)

        valid, msg = cert_generator._validate_certificates(
            "cert.pem", "key.pem")
        assert valid is False
        assert "do not match" in msg


class TestGenerateCertificatePair:
    """Tests for CertificateGenerator.generate_certificate_pair."""

    def test_generate_success(self, monkeypatch, cert_generator):
        """Generate cert/key successfully when no existing files or forced."""
        monkeypatch.setattr(cert_generator, "files_exist", lambda c, k: False)
        monkeypatch.setattr(
            cert_generator,
            "files_exist",
            mock.Mock(
                return_value=False))
        monkeypatch.setattr(cert_generator, "_build_certificate_name",
                            lambda **kwargs: mock.Mock())
        monkeypatch.setattr(cert_generator, "_create_certificate",
                            lambda key, name, dns=None: mock.Mock())
        monkeypatch.setattr(
            cert_generator,
            "_write_private_key",
            lambda key,
            path: None)
        monkeypatch.setattr(
            cert_generator,
            "_write_certificate",
            lambda cert,
            path: None)

        success, msg = cert_generator.generate_certificate_pair()
        assert success is True
        assert "successfully" in msg

    def test_generate_existing_files_no_force(
            self, monkeypatch, cert_generator):
        """Return False and message if files exist and no force overwrite."""
        monkeypatch.setattr(cert_generator, "files_exist", lambda c, k: True)

        success, msg = cert_generator.generate_certificate_pair(
            force_overwrite=False)
        assert success is False
        assert "already exist" in msg

    def test_generate_exception_handling(self, monkeypatch, cert_generator):
        """Return False and error message if exception raised during generation."""
        monkeypatch.setattr(cert_generator, "files_exist", lambda c, k: False)
        monkeypatch.setattr(cert_generator, "_generate_private_key",
                            lambda: (_ for _ in ()).throw(ValueError("fail")))

        success, msg = cert_generator.generate_certificate_pair()
        assert success is False
        assert "Error generating" in msg


class TestEnsureCertificates:
    """Tests for the ensure_certificates function."""

    def test_ensure_certificates_valid_existing(self, monkeypatch, mock_logger):
        """Does nothing if valid certs exist and no force overwrite."""
        gen_mock = mock.Mock()
        gen_mock.files_exist.return_value = True
        gen_mock._validate_certificates.return_value = (True, "valid")
        monkeypatch.setattr(
            certs,
            "CertificateGenerator",
            lambda **kwargs: gen_mock)

        certs.ensure_certificates(force_overwrite=False)

        gen_mock.files_exist.assert_called_once()
        gen_mock._validate_certificates.assert_called_once()
        mock_logger.info.assert_called_with("SSL certificates are valid")

    def test_ensure_certificates_invalid_existing_force(
            self, monkeypatch, mock_logger):
        """Regenerates certs if existing certs are invalid."""
        gen_mock = mock.Mock()
        gen_mock.files_exist.return_value = True
        gen_mock._validate_certificates.return_value = (False, "expired")
        gen_mock.generate_certificate_pair.return_value = (True, "generated")
        monkeypatch.setattr(
            certs,
            "CertificateGenerator",
            lambda **kwargs: gen_mock)

        certs.ensure_certificates(force_overwrite=False)

        gen_mock.generate_certificate_pair.assert_called_once()
        mock_logger.error.assert_called_with(
            "Existing certificates are invalid (%s), regenerating...", "expired"
        )
        mock_logger.info.assert_called_with(
            "SSL certificates generated successfully")

    def test_ensure_certificates_not_exist(self, monkeypatch, mock_logger):
        """Generates certs if files do not exist."""
        gen_mock = mock.Mock()
        gen_mock.files_exist.return_value = False
        gen_mock.generate_certificate_pair.return_value = (True, "generated")
        monkeypatch.setattr(
            certs,
            "CertificateGenerator",
            lambda **kwargs: gen_mock)

        certs.ensure_certificates()

        gen_mock.generate_certificate_pair.assert_called_once()
        mock_logger.debug.assert_any_call(
            "SSL certificates not found, generating new ones...")
        mock_logger.info.assert_called_with(
            "SSL certificates generated successfully")

    def test_ensure_certificates_generation_failure(self, monkeypatch):
        """Raises RuntimeError if generation fails."""
        gen_mock = mock.Mock()
        gen_mock.files_exist.return_value = False
        gen_mock.generate_certificate_pair.return_value = (False, "fail reason")
        monkeypatch.setattr(
            certs,
            "CertificateGenerator",
            lambda **kwargs: gen_mock)

        with pytest.raises(RuntimeError) as excinfo:
            certs.ensure_certificates()
        assert "Certificate generation failed" in str(excinfo.value)
