// POST /v2/bookings: the idempotency-keyed endpoint. The route validates the
// Idempotency-Key header, calls the driving port, maps the outcome to a status
// code (Created/Replayed 201, Conflict 422, InFlight 409) and then runs the
// fault hook. All policy lives in the application layer; only transport here.

package work.rajc.booking.adapter.in.http;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;
import work.rajc.booking.application.port.in.BookSessionIdempotentUseCase;
import work.rajc.booking.application.port.in.BookingOutcome;

@RestController
public class BookingController {

    private final BookSessionIdempotentUseCase useCase;
    private final FaultHook faultHook;

    public BookingController(BookSessionIdempotentUseCase useCase, FaultHook faultHook) {
        this.useCase = useCase;
        this.faultHook = faultHook;
    }

    @PostMapping("/v2/bookings")
    public ResponseEntity<?> create(
            @RequestHeader(value = "Idempotency-Key", required = false) String key,
            @RequestBody BookingRequest booking,
            HttpServletRequest request) {
        if (!isValidKey(key)) {
            return error(HttpStatus.BAD_REQUEST, "idempotency_key_required", null);
        }
        BookingOutcome outcome = useCase.book(key, NaiveBookingController.toCommand(booking));
        faultHook.afterCommit(request);

        return switch (outcome) {
            case BookingOutcome.Conflict ignored -> error(HttpStatus.UNPROCESSABLE_ENTITY, "idempotency_conflict", null);
            case BookingOutcome.InFlight ignored -> error(HttpStatus.CONFLICT, "idempotency_in_flight", "1");
            case BookingOutcome.Replayed replayed -> ResponseEntity.status(HttpStatus.CREATED)
                    .header("Idempotent-Replayed", "true")
                    .body(toResponse(replayed.confirmation()));
            case BookingOutcome.Created created -> ResponseEntity.status(HttpStatus.CREATED)
                    .body(toResponse(created.confirmation()));
        };
    }

    private static boolean isValidKey(String key) {
        if (key == null || key.isEmpty() || key.length() > 255) {
            return false;
        }
        for (int i = 0; i < key.length(); i++) {
            char c = key.charAt(i);
            if (c < '!' || c > '~') {
                return false;
            }
        }
        return true;
    }

    private static ResponseEntity<ErrorResponse> error(HttpStatus status, String code, String retryAfter) {
        org.springframework.http.HttpHeaders headers = new org.springframework.http.HttpHeaders();
        if (retryAfter != null) {
            headers.set("Retry-After", retryAfter);
        }
        return new ResponseEntity<>(new ErrorResponse(code), headers, status);
    }

    private static BookingResponse toResponse(work.rajc.booking.application.port.in.BookingConfirmation confirmation) {
        return new BookingResponse(confirmation.bookingId(), confirmation.chargeId(), confirmation.status());
    }
}
