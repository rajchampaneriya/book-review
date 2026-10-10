package work.rajc.booking.application.port.in;

/**
 * The G2 policy in application terms: Created (this call booked), Replayed (an
 * earlier call with the same key and body booked), Conflict (same key,
 * different body) and InFlight (claimed but no result; a bug if seen). HTTP
 * status codes belong to the inbound adapter, not here.
 */
public sealed interface BookingOutcome {

    record Created(BookingConfirmation confirmation) implements BookingOutcome {
    }

    record Replayed(BookingConfirmation confirmation) implements BookingOutcome {
    }

    record Conflict(String key) implements BookingOutcome {
    }

    record InFlight(String key) implements BookingOutcome {
    }
}
