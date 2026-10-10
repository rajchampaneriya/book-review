// POST /naive/bookings: the control-group endpoint.
//
// INTENTIONALLY NAIVE BASELINE: no idempotency key, no deduplication, no retries,
// no locks. A retried request creates a second booking and a second charge, which
// is exactly what experiment 3 measures. Do not "fix" this.

package work.rajc.booking.adapter.in.http;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import work.rajc.booking.application.port.in.BookSessionCommand;
import work.rajc.booking.application.port.in.BookSessionNaiveUseCase;
import work.rajc.booking.application.port.in.BookingConfirmation;
import work.rajc.booking.domain.InvalidDepositException;

@RestController
public class NaiveBookingController {

    private final BookSessionNaiveUseCase useCase;
    private final FaultHook faultHook;

    public NaiveBookingController(BookSessionNaiveUseCase useCase, FaultHook faultHook) {
        this.useCase = useCase;
        this.faultHook = faultHook;
    }

    @PostMapping("/naive/bookings")
    @ResponseStatus(HttpStatus.CREATED)
    public BookingResponse create(@RequestBody BookingRequest booking, HttpServletRequest request) {
        BookingConfirmation confirmation = useCase.book(toCommand(booking));
        faultHook.afterCommit(request);
        return new BookingResponse(confirmation.bookingId(), confirmation.chargeId(), confirmation.status());
    }

    static BookSessionCommand toCommand(BookingRequest booking) {
        if (booking.clientRef() == null || booking.sessionId() == null
                || booking.dogId() == null || booking.ownerId() == null) {
            throw new InvalidDepositException("all fields are required");
        }
        return new BookSessionCommand(
                booking.clientRef(), booking.sessionId(), booking.dogId(), booking.ownerId(), booking.depositCents());
    }
}
