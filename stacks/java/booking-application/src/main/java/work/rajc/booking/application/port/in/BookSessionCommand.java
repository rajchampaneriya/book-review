package work.rajc.booking.application.port.in;

public record BookSessionCommand(
        String clientRef,
        String sessionId,
        String dogId,
        String ownerId,
        int depositCents) {
}
