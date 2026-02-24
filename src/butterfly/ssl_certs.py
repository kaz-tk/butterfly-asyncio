"""SSL certificate generation for Butterfly.

Generates a self-signed CA + server certificate pair using stdlib ssl/subprocess.
Compatible with the original butterfly's certificate layout.

Files produced in ssl_dir:
  butterfly_ca.crt / butterfly_ca.key         — CA certificate
  butterfly_<host>.crt / butterfly_<host>.key  — Server certificate
"""

import logging
import os
import socket
import stat
import subprocess
from pathlib import Path

logger = logging.getLogger("butterfly.ssl")


def _run_openssl(*args: str) -> None:
    """Run an openssl command, raising on failure."""
    subprocess.run(["openssl", *args], check=True, capture_output=True)


def prepare_ssl_certs(ssl_dir: Path, host: str) -> None:
    """Generate CA + server certificates if they don't exist."""
    ssl_dir.mkdir(parents=True, exist_ok=True)

    ca_crt = ssl_dir / "butterfly_ca.crt"
    ca_key = ssl_dir / "butterfly_ca.key"
    srv_crt = ssl_dir / f"butterfly_{host}.crt"
    srv_key = ssl_dir / f"butterfly_{host}.key"

    hostname = socket.gethostname()

    # --- CA ---
    if not ca_crt.exists() or not ca_key.exists():
        logger.info("Generating CA certificate")
        _run_openssl(
            "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(ca_key),
            "-out", str(ca_crt),
            "-days", "3650",
            "-nodes",
            "-subj",
            f"/C=WW/ST=World Wide/L=Terminal/O=Butterfly"
            f"/OU=Butterfly Terminal/CN=Butterfly CA on {hostname}",
        )
        os.chmod(ca_key, stat.S_IRUSR | stat.S_IWUSR)
        logger.info("CA certificate written to %s", ca_crt)
    else:
        logger.info("CA certificate found at %s", ca_crt)

    # --- Server cert ---
    if not srv_crt.exists() or not srv_key.exists():
        logger.info("Generating server certificate for %s", host)
        csr_path = ssl_dir / f"butterfly_{host}.csr"
        ext_path = ssl_dir / f"butterfly_{host}.ext"

        # SAN extension file
        ext_path.write_text(
            f"subjectAltName=DNS:{host}\n"
            "basicConstraints=CA:FALSE\n"
            "keyUsage=digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n"
        )

        # Generate key + CSR
        _run_openssl(
            "req", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(srv_key),
            "-out", str(csr_path),
            "-subj", f"/C=WW/ST=World Wide/L=Terminal/O=Butterfly/OU=Butterfly Terminal/CN={host}",
        )

        # Sign with CA
        _run_openssl(
            "x509", "-req",
            "-in", str(csr_path),
            "-CA", str(ca_crt),
            "-CAkey", str(ca_key),
            "-CAcreateserial",
            "-out", str(srv_crt),
            "-days", "3650",
            "-extfile", str(ext_path),
        )

        os.chmod(srv_key, stat.S_IRUSR | stat.S_IWUSR)

        # Clean up temp files
        csr_path.unlink(missing_ok=True)
        ext_path.unlink(missing_ok=True)
        (ssl_dir / "butterfly_ca.srl").unlink(missing_ok=True)

        logger.info("Server certificate written to %s", srv_crt)
    else:
        logger.info("Server certificate found at %s", srv_crt)


def get_ssl_paths(ssl_dir: Path, host: str) -> dict[str, str] | None:
    """Return uvicorn ssl kwargs if certs exist, else None."""
    ca_crt = ssl_dir / "butterfly_ca.crt"
    srv_crt = ssl_dir / f"butterfly_{host}.crt"
    srv_key = ssl_dir / f"butterfly_{host}.key"

    if all(p.exists() for p in (ca_crt, srv_crt, srv_key)):
        return {
            "ssl_certfile": str(srv_crt),
            "ssl_keyfile": str(srv_key),
            "ssl_ca_certs": str(ca_crt),
        }
    return None
