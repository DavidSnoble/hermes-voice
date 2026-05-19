"""Loads the same context Hermes loads at startup."""

import os
from pathlib import Path

import yaml

from hermes_voice.domain.entities import HermesContext, Persona, UserContext
from hermes_voice.domain.ports import ContextProvider


class HermesContextProvider(ContextProvider):
    """
    Reads Hermes configuration from ~/.hermes/:
      - SOUL.md          → persona identity
      - memories/MEMORY.md → environment facts
      - memories/USER.md   → user profile
      - config.yaml      → model/toolset config
    """

    def __init__(self, hermes_home: str | None = None) -> None:
        self._home = Path(hermes_home or os.path.expanduser("~/.hermes"))

    async def load(self) -> HermesContext:
        persona = self._load_persona()
        user = self._load_user()
        env = self._load_environment()
        config = self._load_config()
        return HermesContext(
            persona=persona,
            user=user,
            environment_notes=env,
            config=config,
        )

    def _load_persona(self) -> Persona:
        soul_path = self._home / "SOUL.md"
        identity = "You are a helpful AI assistant."
        quirks: list[str] = []

        if soul_path.exists():
            content = soul_path.read_text(encoding="utf-8")
            # Extract text between <!-- --> markers if present,
            # otherwise treat the whole file as the persona.
            if "<!--" in content:
                parts = content.split("-->", 1)
                if len(parts) > 1:
                    body = parts[1].strip()
                else:
                    body = content.strip()
            else:
                body = content.strip()

            if body:
                identity = body
                # Simple heuristic: lines starting with "-" are quirks
                for line in body.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("-") or stripped.startswith("•"):
                        quirks.append(stripped.lstrip("-• ").strip())

        return Persona(
            identity=identity,
            voice_style="concise",
            quirks=quirks,
        )

    def _load_user(self) -> UserContext:
        user_path = self._home / "memories" / "USER.md"
        user = UserContext(name="User")

        if user_path.exists():
            content = user_path.read_text(encoding="utf-8")
            # Parse simple key-value-ish lines
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("§"):
                    continue
                if "David Snoble" in line:
                    user.name = "David Snoble"
                if "Calgary" in line and "from" in line:
                    user.location = "Calgary, AB"
                    user.timezone = "America/Edmonton"
                if "Works at" in line or "Previously:" in line:
                    user.job = line.split(".")[0]
                if "ADHD" in line:
                    user.adhd_scaffolding = True
                if "salary" in line.lower() or "$" in line:
                    user.facts.append(line)
                if "prefers" in line.lower() or "Values" in line:
                    user.facts.append(line)

        # If parsing failed, at least keep raw facts
        if not user.facts and user_path.exists():
            user.facts = [
                f.strip()
                for f in user_path.read_text(encoding="utf-8").split("§")
                if f.strip()
            ]

        return user

    def _load_environment(self) -> str:
        memory_path = self._home / "memories" / "MEMORY.md"
        if memory_path.exists():
            return memory_path.read_text(encoding="utf-8").strip()
        return ""

    def _load_config(self) -> dict:
        config_path = self._home / "config.yaml"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
        return {}
