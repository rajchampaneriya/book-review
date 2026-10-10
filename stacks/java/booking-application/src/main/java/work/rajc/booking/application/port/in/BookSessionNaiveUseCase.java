package work.rajc.booking.application.port.in;

public interface BookSessionNaiveUseCase {

    BookingConfirmation book(BookSessionCommand command);
}
