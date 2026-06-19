"""KDEck KDE Connect TLS utilities — certificate generation and peer fingerprint.

All functions here are stateless. Paths are passed as arguments rather than
read from instance attributes.
"""

import datetime
import hashlib
import os
import shutil
import ssl
import subprocess
from pathlib import Path
from typing import Optional


def _generate_cert_with_cryptography(cert_path: Path, key_path: Path, device_id: str) -> None:
    """Generate a self-signed certificate using the ``cryptography`` library."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, device_id)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )

    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)

    key_path.write_bytes(key_pem)
    cert_path.write_bytes(cert_pem)
    try:
        os.chmod(key_path, 0o600)
    except OSError:
        pass


def _generate_cert_with_openssl(cert_path: Path, key_path: Path, device_id: str) -> None:
    """Generate a self-signed certificate using the ``openssl`` CLI."""
    openssl = shutil.which("openssl")
    if not openssl:
        raise RuntimeError("openssl not found, cannot generate KDEck KDE Connect certificate.")

    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/home/deck",
        "USER": "deck",
        "LOGNAME": "deck",
        "LANG": "en_US.UTF-8",
    }
    result = subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "3650",
            "-subj",
            f"/CN={device_id}",
        ],
        env=env,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "openssl req failed").strip())
    os.chmod(key_path, 0o600)


def ensure_certificate(
    cert_path: Path,
    key_path: Path,
    device_id: str,
) -> bool:
    """Ensure a self-signed TLS certificate exists for KDE Connect.

    Prefers the ``cryptography`` Python library (cross-platform, no external
    tools required).  Falls back to the ``openssl`` CLI when ``cryptography``
    is not installed.

    Returns True if the certificate already existed, False if it was generated.
    Raises RuntimeError when generation fails.
    """
    if cert_path.exists() and key_path.exists():
        return True

    try:
        _generate_cert_with_cryptography(cert_path, key_path, device_id)
        return False
    except ImportError:
        pass

    _generate_cert_with_openssl(cert_path, key_path, device_id)
    return False


def peer_fingerprint(tls: ssl.SSLSocket) -> Optional[str]:
    """Return the SHA-256 fingerprint of the peer's TLS certificate, or None."""
    try:
        cert = tls.getpeercert(binary_form=True)
    except (ssl.SSLError, ValueError):
        cert = None
    if not cert:
        return None
    return hashlib.sha256(cert).hexdigest()
