"""request_hash: the lowercase hex SHA-256 of the canonical request string
(client_ref, session_id, dog_id, owner_id and deposit_cents in decimal, joined
by newlines), exactly as docs/exp3-spec.md defines it."""

from __future__ import annotations

import hashlib

from booking.application.ports.inbound import BookSessionCommand


def request_hash(command: BookSessionCommand) -> str:
    canonical = "\n".join(
        (
            command.client_ref,
            command.session_id,
            command.dog_id,
            command.owner_id,
            str(command.deposit_cents),
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
