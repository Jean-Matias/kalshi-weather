import base64
import tempfile
import unittest
from pathlib import Path

from nacl.signing import SigningKey

from robinhood_crypto_bot.generate_keys import generate_and_store_keypair


class RobinhoodKeygenTests(unittest.TestCase):
    def test_generates_matching_keypair_and_preserves_other_env_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "ROBINHOOD_API_KEY=\nBOT_DRY_RUN=true\nBOT_ALLOW_LIVE_ORDERS=false\n",
                encoding="ascii",
            )

            public_key = generate_and_store_keypair(env_path)
            env_text = env_path.read_text(encoding="ascii")
            private_key = next(
                line.split("=", 1)[1]
                for line in env_text.splitlines()
                if line.startswith("ROBINHOOD_PRIVATE_KEY_BASE64=")
            )

            self.assertEqual(32, len(base64.b64decode(public_key)))
            derived_public_key = SigningKey(base64.b64decode(private_key)).verify_key.encode()
            self.assertEqual(base64.b64decode(public_key), derived_public_key)
            self.assertIn("ROBINHOOD_PRIVATE_KEY_BASE64=", env_text)
            self.assertIn("BOT_DRY_RUN=true", env_text)
            self.assertIn("BOT_ALLOW_LIVE_ORDERS=false", env_text)
            self.assertNotIn(public_key, env_text)

    def test_refuses_to_replace_an_existing_private_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "ROBINHOOD_PRIVATE_KEY_BASE64=already-configured\n",
                encoding="ascii",
            )

            with self.assertRaisesRegex(RuntimeError, "already contains"):
                generate_and_store_keypair(env_path)


if __name__ == "__main__":
    unittest.main()
