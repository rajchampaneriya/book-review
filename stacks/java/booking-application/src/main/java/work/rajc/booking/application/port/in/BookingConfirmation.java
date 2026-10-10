package work.rajc.booking.application.port.in;

public record BookingConfirmation(
        String bookingId,
        String chargeId,
        String status) {
}
