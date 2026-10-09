# P6 (stretch). The booking as an MCP tool

**Only start if** experiment 3 is complete in every stack by Sat 10 Oct, 20:00 IST.
**Session:** a new Claude Code session in plan mode.

## Prompt (paste as is)

```text
Read CLAUDE.md and docs/exp3-spec.md first.

Task: expose the booking as an MCP tool named book_session in the FastAPI stack, using the official MCP Python SDK v2 (protocol revision 2026-07-28), served at /mcp. Build it as a second inbound adapter, exactly the optional entries in the CLAUDE.md tree (src/booking/adapters/inbound/mcp/__init__.py, schemas.py, tools.py), that calls the same BookSessionIdempotentUseCase port as the HTTP adapter and shares its idempotency table. The MCP adapter must not import the HTTP adapter; anything both need belongs in the application layer. Bootstrap mounts both.

- Tool input schema: session_id, dog_id, owner_id, deposit_cents, client_ref and idempotency_key, all required, as an explicit Pydantic model with extra="forbid" (rule G1).
- Same idempotency semantics as /v2/bookings: one booking per key, replay on repeat, conflict on a different body.
- Set readOnlyHint, destructiveHint and idempotentHint truthfully according to the 2026-07-28 spec, and explain each choice in a code comment.
- Read the SDK's current documentation before writing code. Do not rely on memory of v1 APIs.
- Add the contract test contracts/tests/test_mcp_tool.py (optional in the tree) using the SDK's client: calling the tool twice with the same idempotency_key creates one booking. Add the SDK to pyproject.toml and requirements-host.txt; no other new files.

Plan first, wait for approval. Done when the new test passes, and python3 tools/arch/check_hexagonal.py --all, make arch STACK=python and make contract STACK=python still pass. Do not push.
```
