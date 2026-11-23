"""Escribe la configuración privada de OCI y SSH en el runner."""

import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen


def required(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Falta configurar {name}.")
    return value


def write_private(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(content)
    path.chmod(0o600)


def validate_ssh_pair(private_path, public_key, label):
    generated = subprocess.run(["ssh-keygen", "-y", "-P", "", "-f", str(private_path)],
                               capture_output=True, text=True)
    expected = public_key.split()[:2]
    if generated.returncode or len(expected) != 2 or generated.stdout.split()[:2] != expected:
        raise SystemExit(f"El par de claves SSH {label} no coincide o la clave privada requiere una passphrase.")


def main():
    for name in ("NOTES_PASSWORD_1", "NOTES_PASSWORD_2"):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{16,128}", required(name)):
            raise SystemExit(f"{name} debe contener entre 16 y 128 caracteres URL-safe.")
    domain = os.getenv("NOTES_DOMAIN", "")
    if domain:
        if not re.fullmatch(r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9]+", domain):
            raise SystemExit("NOTES_DOMAIN debe ser un nombre de dominio sin protocolo ni ruta.")
        for name in ("CLOUDFLARE_ZONE_ID", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ORIGIN_CERT", "CLOUDFLARE_ORIGIN_KEY"):
            required(name)

    home = Path.home()
    ssh_key = home / ".ssh" / "notes"
    host_key = home / ".ssh" / "notes-host"
    host_pem = required("SSH_HOST_PRIVATE_KEY").replace("\r\n", "\n") + "\n"
    write_private(ssh_key, required("SSH_PRIVATE_KEY").replace("\r\n", "\n") + "\n")
    write_private(host_key, host_pem)
    ssh_public = required("SSH_PUBLIC_KEY")
    host_public = required("SSH_HOST_PUBLIC_KEY")
    validate_ssh_pair(ssh_key, ssh_public, "de acceso")
    validate_ssh_pair(host_key, host_public, "del servidor")
    if not host_public.startswith("ssh-ed25519 "):
        raise SystemExit("SSH_HOST_PUBLIC_KEY debe ser una clave Ed25519.")

    region = required("OCI_REGION")
    api_key = home / ".oci" / "notes.pem"
    write_private(api_key, required("OCI_API_KEY") + "\n")
    write_private(home / ".oci" / "config", "\n".join([
        "[DEFAULT]", f"user={required('OCI_USER_OCID')}", f"tenancy={required('OCI_TENANCY_OCID')}",
        f"fingerprint={required('OCI_FINGERPRINT')}", f"region={region}", f"key_file={api_key}", "",
    ]))
    with urlopen("https://api.ipify.org", timeout=20) as response:
        runner_ip = ipaddress.IPv4Address(response.read().decode().strip())

    settings = {
        "region": region,
        "compartment_id": required("OCI_COMPARTMENT_OCID"),
        "availability_domain": required("OCI_AVAILABILITY_DOMAIN"),
        "ubuntu_image_id": required("OCI_UBUNTU_IMAGE_OCID"),
        "instance_shape": required("OCI_SHAPE"),
        "ssh_cidr": f"{runner_ip}/32",
        "ssh_public_key": ssh_public,
        "ssh_host_public_key": host_public,
        "ssh_host_private_key": host_pem,
    }
    write_private("infra/terraform/notes.auto.tfvars.json", json.dumps(settings))
    backend = {"bucket": required("OCI_STATE_BUCKET"), "namespace": required("OCI_NAMESPACE"),
               "region": region, "key": "notas-en-accion/production.tfstate"}
    write_private("infra/terraform/backend.hcl", "\n".join(f"{key} = {json.dumps(value)}" for key, value in backend.items()))


if __name__ == "__main__":
    main()
