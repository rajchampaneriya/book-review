package work.rajc.booking.adapter.in.http;

public record BookingResponse(
        String booking_id,
        String charge_id,
        String status) {
}
