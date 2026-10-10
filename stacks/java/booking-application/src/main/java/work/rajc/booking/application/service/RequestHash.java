package work.rajc.booking.application.service;

import work.rajc.booking.application.port.in.BookSessionCommand;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/**
 * The lowercase hex SHA-256 of the canonical request string (client_ref,
 * session_id, dog_id, owner_id and deposit_cents in decimal, joined by
 * newlines), exactly as docs/exp3-spec.md defines it.
 */
public final class RequestHash {

    private RequestHash() {
    }

    public static String compute(BookSessionCommand command) {
        String canonical = String.join("\n",
                command.clientRef(),
                command.sessionId(),
                command.dogId(),
                command.ownerId(),
                Integer.toString(command.depositCents()));
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(canonical.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is unavailable", e);
        }
    }
}
