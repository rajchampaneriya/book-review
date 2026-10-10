package work.rajc.booking.application.port.in;

public interface BookSessionIdempotentUseCase {

    BookingOutcome book(String key, BookSessionCommand command);
}
