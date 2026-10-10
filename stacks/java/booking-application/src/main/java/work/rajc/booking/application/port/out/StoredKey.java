package work.rajc.booking.application.port.out;

import java.util.Map;
import java.util.Optional;

/** A stored idempotency key: its request hash and, after a commit, its result. */
public record StoredKey(
        String key,
        String requestHash,
        Map<String, String> result) {

    public Optional<Map<String, String>> resultOrNull() {
        return Optional.ofNullable(result);
    }
}
