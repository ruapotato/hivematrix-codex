import os
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Define the output directory for certificates
CERT_DIR = "certs"
CERT_FILE = os.path.join(CERT_DIR, "cert.pem")
KEY_FILE = os.path.join(CERT_DIR, "key.pem")

def generate_certs():
    """
    Generates a self-signed SSL certificate and a private key.
    Saves them to the 'certs' directory.
    """
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print("Certificates already exist in the 'certs/' directory. Skipping generation.")
        return

    print("Generating self-signed SSL certificates...")

    # Create the certs directory if it doesn't exist
    if not os.path.exists(CERT_DIR):
        os.makedirs(CERT_DIR)

    # Generate our key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Write our key to a file
    with open(KEY_FILE, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    print(f"Private key saved to {KEY_FILE}")

    # Various details for our certificate.
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Oregon"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Sutherlin"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"HiveMatrix Nexus Development"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        # Our certificate will be valid for 10 years
        datetime.utcnow() + timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
        critical=False,
    # Sign our certificate with our private key
    ).sign(key, hashes.SHA256(), default_backend())

    # Write our certificate out to a file.
    with open(CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Certificate saved to {CERT_FILE}")
    print("\nCertificate generation complete.")

if __name__ == "__main__":
    generate_certs()
