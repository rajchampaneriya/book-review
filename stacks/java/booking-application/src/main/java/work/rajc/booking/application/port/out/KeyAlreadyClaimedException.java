package work.rajc.booking.application.port.out;

/**
 * The idempotency key is already claimed; the attempted transaction was rolled
 * back. The Postgres adapter translates SQLSTATE 23505 into this exception; no
 * driver exception crosses the port.
 */
public class KeyAlreadyClaimedException extends RuntimeException {

    public KeyAlreadyClaimedException(String message) {
        super(message);
    }
}
