import re

from hermes_voice.domain.entities import Conversation, Intent, IntentType
from hermes_voice.domain.ports import IntentClassifierPort


class KeywordIntentClassifier(IntentClassifierPort):
    """
    Fast keyword-based intent classifier. No LLM call — instant.

    DELEGATE: multi-step tasks (coding, writing, research, system changes)
    QUICK_TOOL: single lookups (weather, search, read file)
    CONVERSATION: everything else (chitchat, opinions, simple Q&A)
    """

    DELEGATE_PATTERNS = [
        r"\b(refactor|code|rewrite|fix\s+bug|debug|implement|build\s+app|deploy|configure|setup)\b",
        r"\b(research|look\s+up|investigate|compare|analyze\s+data|study|deep\s+dive)\b",
        r"\b(write|draft|generate|create\s+(?:blog|post|article|email|letter|report|doc))\b",
        r"\b(plan|schedule|organize|manage|project|multi.step|complex)\b",
        r"\b(update|upgrade|migrate|change\s+(?:system|config|setting))\b",
    ]

    QUICK_TOOL_PATTERNS = [
        r"\b(weather|temperature|forecast)\b",
        r"\b(search|google|look\s+up|find)\b",
        r"\b(read|show|open|get)\b.*\b(file|doc|document|note|log)\b",
        r"\b(what\s+time|when|what\s+day|calendar|remind)\b",
        r"\b(convert|calculate|math|sum|average)\b",
        r"\b(check|status|health|ping)\b",
    ]

    def __init__(self) -> None:
        self._delegate_re = re.compile("|".join(self.DELEGATE_PATTERNS), re.IGNORECASE)
        self._quick_tool_re = re.compile("|".join(self.QUICK_TOOL_PATTERNS), re.IGNORECASE)

    async def classify(self, transcript: str, conversation: Conversation) -> Intent:
        text = transcript.lower()

        if self._delegate_re.search(text):
            return Intent(IntentType.DELEGATE, confidence=0.85, reasoning="keyword_match_delegate")

        if self._quick_tool_re.search(text):
            return Intent(IntentType.QUICK_TOOL, confidence=0.8, reasoning="keyword_match_quick_tool")

        return Intent(IntentType.CONVERSATION, confidence=0.95, reasoning="default_conversation")

    async def close(self) -> None:
        pass
