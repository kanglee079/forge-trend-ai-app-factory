#!/usr/bin/env python3
from pathlib import Path

from cryptography.fernet import Fernet


env_path = Path(".env")
if not env_path.exists():
    env_path.write_text(Path(".env.example").read_text(), encoding="utf-8")

text = env_path.read_text(encoding="utf-8")
if "FACTORY_SECRET_KEY=replace-with-fernet-key" in text:
    text = text.replace(
        "FACTORY_SECRET_KEY=replace-with-fernet-key",
        f"FACTORY_SECRET_KEY={Fernet.generate_key().decode()}",
    )
    env_path.write_text(text, encoding="utf-8")
