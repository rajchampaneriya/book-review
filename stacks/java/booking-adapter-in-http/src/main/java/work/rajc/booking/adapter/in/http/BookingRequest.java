package work.rajc.booking.adapter.in.http;

/** Inbound DTO; unknown fields are rejected (rule G1, via Jackson config). */
public record BookingRequest(
        String clientRef,
        String sessionId,
        String dogId,
        String ownerId,
        int depositCents) {
}
