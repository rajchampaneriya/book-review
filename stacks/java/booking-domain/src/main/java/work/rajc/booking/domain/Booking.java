package work.rajc.booking.domain;

import java.util.UUID;

public record Booking(
        UUID id,
        String clientRef,
        String sessionId,
        String dogId,
        String ownerId,
        DepositAmount deposit) {
}
