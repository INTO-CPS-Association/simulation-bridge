"""Certificate generator module with file existence checking."""

import datetime
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from ..utils.logger import get_logger

logger = get_logger()

class CertificateGenerator:
    """Class for generating SSL certificates and private keys."""

    def __init__(
        self,
        key_size: int = 2048,
        public_exponent: int = 65537,
        validity_days: int = 365
    ) -> None:
        """
        Initialize certificate generator.

        Args:
            key_size: RSA key size in bits
            public_exponent: RSA public exponent
            validity_days: Certificate validity in days
        """
        self.key_size = key_size
        self.public_exponent = public_exponent
        self.validity_days = validity_days

    def _generate_private_key(self) -> rsa.RSAPrivateKey:
        """
        Generate RSA private key.

        Returns:
            RSA private key instance
        """
        return rsa.generate_private_key(
            public_exponent=self.public_exponent,
            key_size=self.key_size,
        )

    def _build_certificate_name( # pylint: disable=too-many-arguments
        self,
        country: str = "US",
        state: str = "California",
        locality: str = "San Francisco",
        organization: str = "My Company",
        common_name: str = "localhost"
    ) -> x509.Name:
        """
        Build X.509 certificate name.

        Args:
            country: Country name
            state: State or province name
            locality: Locality name
            organization: Organization name
            common_name: Common name

        Returns:
            X.509 Name object
        """
        return x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, locality),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

    def _create_certificate(
        self,
        private_key: rsa.RSAPrivateKey,
        subject_name: x509.Name,
        dns_names: Optional[list] = None
    ) -> x509.Certificate:
        """
        Create X.509 certificate.

        Args:
            private_key: Private key for signing
            subject_name: Subject name for certificate
            dns_names: List of DNS names for SAN extension

        Returns:
            X.509 certificate
        """
        if dns_names is None:
            dns_names = ["localhost"]

        now = datetime.datetime.now(datetime.timezone.utc)
        cert_builder = (
            x509.CertificateBuilder()
            .subject_name(subject_name)
            .issuer_name(subject_name)  # Self-signed
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=self.validity_days))
        )

        # Add Subject Alternative Name extension
        san_list = [x509.DNSName(name) for name in dns_names]
        cert_builder = cert_builder.add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )

        return cert_builder.sign(private_key, hashes.SHA256())

    def files_exist(self, cert_path: str, key_path: str) -> bool:
        """
        Check if certificate and key files already exist.

        Args:
            cert_path: Path to certificate file
            key_path: Path to private key file

        Returns:
            True if both files exist, False otherwise
        """
        cert_file = Path(cert_path)
        key_file = Path(key_path)
        return cert_file.exists() and key_file.exists()

    def _validate_certificates( #pylint: disable=too-many-locals
            self, cert_path: str, key_path: str) -> Tuple[bool, str]:
        """
        Validate existing certificate and key files.

        Args:
            cert_path: Path to certificate file
            key_path: Path to private key file

        Returns:
            Tuple of (is_valid: bool, reason: str)
        """
        try:
            # Load certificate
            with open(cert_path, "rb") as cert_file:
                cert_data = cert_file.read()
                certificate = x509.load_pem_x509_certificate(cert_data)

            # Load private key
            with open(key_path, "rb") as key_file:
                key_data = key_file.read()
                private_key = serialization.load_pem_private_key(
                    key_data, password=None)

            # Check if certificate has expired
            now = datetime.datetime.now(datetime.timezone.utc)
            if certificate.not_valid_after_utc < now:
                return False, "Certificate has expired"

            # Check if certificate is not yet valid
            if certificate.not_valid_before_utc > now:
                return False, "Certificate is not yet valid"

            # Check if certificate is expiring soon (within 30 days)
            expires_soon = now + datetime.timedelta(days=30)
            if certificate.not_valid_after_utc < expires_soon:
                days_left = (certificate.not_valid_after_utc - now).days
                return False, f"Certificate expires in {days_left} days"

            # Verify that the private key matches the certificate
            cert_public_key = certificate.public_key()
            private_public_key = private_key.public_key()

            # Compare key sizes and public numbers for RSA keys
            if (hasattr(cert_public_key, 'key_size') and
                    hasattr(private_public_key, 'key_size')):
                if cert_public_key.key_size != private_public_key.key_size:
                    return False, "Certificate and private key do not match"

                cert_numbers = cert_public_key.public_numbers()
                private_numbers = private_public_key.public_numbers()
                if (cert_numbers.n != private_numbers.n or
                        cert_numbers.e != private_numbers.e):
                    return False, "Certificate and private key do not match"

            return True, "Certificates are valid"

        except FileNotFoundError as exc:
            return False, f"Certificate file not found: {exc}"
        except Exception as exc: # pylint: disable=broad-except
            return False, f"Certificate validation error: {exc}"

    def _ensure_directory_exists(self, file_path: str) -> None:
        """
        Ensure the directory for the file path exists.

        Args:
            file_path: Full path to file
        """
        directory = Path(file_path).parent
        directory.mkdir(parents=True, exist_ok=True)

    def _write_private_key(
        self,
        private_key: rsa.RSAPrivateKey,
        key_path: str
    ) -> None:
        """
        Write private key to file.

        Args:
            private_key: Private key to write
            key_path: Path to write key file
        """
        self._ensure_directory_exists(key_path)

        key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(key_path, "wb") as key_file:
            key_file.write(key_bytes)

    def _write_certificate(
            self, certificate: x509.Certificate, cert_path: str) -> None:
        """
        Write certificate to file.

        Args:
            certificate: Certificate to write
            cert_path: Path to write certificate file
        """
        self._ensure_directory_exists(cert_path)

        cert_bytes = certificate.public_bytes(serialization.Encoding.PEM)

        with open(cert_path, "wb") as cert_file:
            cert_file.write(cert_bytes)

    def generate_certificate_pair(
        self,
        cert_path: str = "certs/cert.pem",
        key_path: str = "certs/key.pem",
        force_overwrite: bool = False,
        **name_kwargs
    ) -> Tuple[bool, str]:
        """
        Generate certificate and private key pair.

        Args:
            cert_path: Path for certificate file
            key_path: Path for private key file
            force_overwrite: Whether to overwrite existing files
            **name_kwargs: Additional arguments for certificate name

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if files already exist
            if self.files_exist(cert_path, key_path) and not force_overwrite:
                return False, f"Files already exist: {cert_path}, {key_path}. Use force_overwrite=True to overwrite." # pylint: disable=line-too-long

            # Generate private key
            private_key = self._generate_private_key()

            # Build certificate name
            subject_name = self._build_certificate_name(**name_kwargs)

            # Create certificate
            certificate = self._create_certificate(private_key, subject_name)

            # Write files
            self._write_private_key(private_key, key_path)
            self._write_certificate(certificate, cert_path)

            return True, f"Certificate and key generated successfully: {cert_path}, {key_path}"

        except Exception as exc: # pylint: disable=broad-except
            return False, f"Error generating certificate: {str(exc)}"


def ensure_certificates(
    cert_path: str = "certs/cert.pem",
    key_path: str = "certs/key.pem",
    validity_days: int = 365,
    force_overwrite: bool = False,
    **name_kwargs
) -> None:
    """
    Ensure SSL certificates exist, generate them if missing.

    This function handles all certificate logic internally and raises
    exceptions on failure, making it simple to use from other modules.

    Args:
        cert_path: Path for certificate file
        key_path: Path for private key file
        validity_days: Certificate validity in days
        force_overwrite: Whether to overwrite existing files
        **name_kwargs: Additional arguments for certificate name (country, state, etc.)

    Raises:
        RuntimeError: If certificate generation fails
    """

    generator = CertificateGenerator(validity_days=validity_days)

    # Check if certificates already exist
    if generator.files_exist(cert_path, key_path):
        # Validate existing certificates
        is_valid, reason = generator._validate_certificates( # pylint: disable=protected-access
            cert_path, key_path)

        if is_valid and not force_overwrite:
            logger.info(
                "SSL certificates are valid")
            logger.debug(
                "Certificate path: %s, Key path: %s", cert_path, key_path)
            return
        if not is_valid:
            logger.error(
                "Existing certificates are invalid (%s), regenerating...",
                reason)
            force_overwrite = True
        if force_overwrite:
            logger.debug(
                "Force overwrite requested, regenerating certificates...")
    else:
        logger.debug("SSL certificates not found, generating new ones...")

    # Generate certificates
    success, message = generator.generate_certificate_pair(
        cert_path=cert_path,
        key_path=key_path,
        force_overwrite=force_overwrite,
        **name_kwargs
    )

    if success:
        logger.info("SSL certificates generated successfully")
        logger.debug("Certificate path: %s, Key path: %s", cert_path, key_path)
    else:
        logger.error("Failed to generate SSL certificates: %s", message)
        raise RuntimeError(f"Certificate generation failed: {message}")
