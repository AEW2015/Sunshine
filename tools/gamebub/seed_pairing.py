"""@brief Prepare a new isolated Sunshine state file for one known client certificate.

This does not change the running Sunshine installation, create a private key,
configure the Web UI, or select an ESP32 transport. It is useful only if the
agreed client ultimately supports Sunshine's certificate-based control path.
"""

import argparse
import hashlib
import json
import re
import ssl
import uuid
from pathlib import Path


def seed_state(certificate: str, output: Path) -> str:
    """@brief Write a new single-client Sunshine state with a validated public certificate.

    @param certificate Exactly one PEM-encoded public X.509 certificate.
    @param output New state file path; an existing file is never overwritten.
    @return SHA-256 fingerprint of the DER certificate, in lowercase hexadecimal.
    @throws ValueError If the input is not exactly one parseable public certificate.
    @throws OSError If the output cannot be created exclusively.
    """
    pem = certificate.strip()
    if not re.fullmatch(
        r"-----BEGIN CERTIFICATE-----\s*[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----", pem
    ):
        raise ValueError("Expected exactly one public PEM certificate and no other material")
    try:
        der = ssl.PEM_cert_to_DER_cert(pem)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=pem)
    except (ValueError, ssl.SSLError) as error:
        raise ValueError("Invalid X.509 certificate") from error
    state = {
        "root": {
            "uniqueid": str(uuid.uuid4()),
            "named_devices": [
                {"name": "Game Bub", "cert": pem + "\n", "uuid": str(uuid.uuid4()), "enabled": True}
            ],
        }
    }
    with output.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(state, file, indent=2)
        file.write("\n")
    return hashlib.sha256(der).hexdigest()


def main(argv=None):
    """@brief Create a separate state file; print only its public certificate fingerprint.

    @param argv Optional argument list for the certificate and new output file.
    @return Zero when the isolated state was created successfully.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-cert", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        fingerprint = seed_state(args.client_cert.read_text(encoding="utf-8"), args.output)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Created new state for Game Bub; certificate SHA-256: {fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
