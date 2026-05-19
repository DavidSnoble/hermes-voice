"""Loads lightweight Hermes persona + user context for the voice agent."""

import os
from pathlib import Path

from hermes_voice.domain.entities import AgentContext, Persona, UserContext
from hermes_voice.domain.ports import ContextProvider


class HermesContextProvider(ContextProvider):
    """
    Reads only the PERSONALITY and USER context from ~/.hermes/:
      - SOUL.md          → persona identity
      - memories/USER.md → user profile
      - memories/MEMORY.md → optional environment notes (lightweight)

    Does NOT load the full tool registry or config — the voice agent is
    lightweight and delegates complex work to the Hermes gateway.
    """

    def __init__(self, hermes_home: str | None = None) -> None:
        self._home = Path(hermes_home or os.path.expanduser("~/.hermes"))

    async def load(self) -> AgentContext:
        persona = self._load_persona()
        user = self._load_user()
        return AgentContext(persona=persona, user=user)

    def _load_persona(self) -> Persona:
        soul_path = self._home / "SOUL.md"
        identity = "You are Hermes, a helpful AI assistant."

        if soul_path.exists():
            content = soul_path.read_text(encoding="utf-8")
            # Extract text after <!-- --> markers
            if "<!--" in content:
                parts = content.split("-->", 1)
                body = parts[1].strip() if len(parts) > 1 else content.strip()
            else:
                body = content.strip()
            if body:
                identity = body

        return Persona(identity=identity, voice_style="concise")

    def _load_user(self) -> UserContext:
        user_path = self._home / "memories" / "USER.md"
        user = UserContext(name="User")

        if user_path.exists():
            content = user_path.read_text(encoding="utf-8")
            sections = [s.strip() for s in content.split("§") if s.strip()]

            for section in sections:
                lines = [l.strip() for l in section.splitlines() if l.strip()]
                for line in lines:
                    if "David Snoble" in line or "name" in line.lower():
                        user.name = "David Snoble"
                    if "Calgary" in line:
                        user.location = "Calgary, AB"
                        user.timezone = "America/Edmonton"
                    if "Works at" in line or "Previously:" in line:
                        user.job = "Software developer"
                    if "ADHD" in line:
                        user.adhd_scaffolding = True
                    if any(k in line.lower() for k in ("prefers", "values", "salary", "debt", "budget")):
                        user.facts.append(line)

        # Fallback: if we didn't parse well, keep raw sections as facts
        if not user.facts and user_path.exists():
            user.facts = sections[:10]  # limit to avoid token bloat

        return user
