package work.rajc.booking.domain;

import java.util.UUID;

/** A simulated charge; there is no payment provider (rule G7). */
public record Charge(
        UUID id,
        UUID bookingId,
        String clientRef,
        int amountCents) {
}
