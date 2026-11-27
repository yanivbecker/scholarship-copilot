"""The AI-use rules gate (FR-A1, FR-A2). Filled in fully in milestone 7.2.

CLAUDE.md: "AI-policy check before any writing help. Unclear rules count as
no AI writing." So AI help is allowed only when the student has confirmed a
rules check whose result is ALLOWED. Everything else, including "not checked
yet", means no AI writing help of any kind.
"""

from app.modules.packets.models import Packet, RulesStatus


def ai_writing_allowed(packet: Packet) -> bool:
    return (
        packet.rules_status is RulesStatus.ALLOWED
        and packet.rules_confirmed_at is not None
    )
