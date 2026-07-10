from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

from nacl.signing import SigningKey

PRIVATE_KEY_NAME = "ROBINHOOD_PRIVATE_KEY_BASE64"


def _env_value(text: str, name: str) -> str | None:
    prefix = f"{name}="
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _set_env_value(text: str, name: str, value: str) -> str:
    prefix = f"{name}="
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{prefix}{value}"
            break
    else:
        lines.append(f"{prefix}{value}")
    return "\n".join(lines) + "\n"


def generate_and_store_keypair(env_path: Path) -> str:
    env_path = env_path.resolve()
    if env_path.exists():
        env_text = env_path.read_text(encoding="ascii")
    else:
        example_path = env_path.with_name(".env.example")
        env_text = example_path.read_text(encoding="ascii") if example_path.exists() else ""

    if _env_value(env_text, PRIVATE_KEY_NAME):
        raise RuntimeError(f"{env_path} already contains a Robinhood private key.")

    signing_key = SigningKey.generate()
    private_key = base64.b64encode(signing_key.encode()).decode("ascii")
    public_key = base64.b64encode(signing_key.verify_key.encode()).decode("ascii")

    env_path.write_text(
        _set_env_value(env_text, PRIVATE_KEY_NAME, private_key),
        encoding="ascii",
    )
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass
    return public_key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Robinhood Crypto Ed25519 key pair locally."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).with_name(".env"),
        help="Private-key destination (default: robinhood_crypto_bot/.env).",
    )
    args = parser.parse_args()

    public_key = generate_and_store_keypair(args.env_file)
    print("Robinhood public key (safe to paste into Robinhood):")
    print(public_key)
    print("Private key saved locally; it was not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
