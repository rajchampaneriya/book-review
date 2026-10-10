// BookSessionNaiveService: the control group.
//
// INTENTIONALLY NAIVE BASELINE: no idempotency key, no deduplication, no retries,
// no locks, no unique constraints. One transaction: insert the booking, insert the
// charge, commit. A retried request creates a second booking and a second charge,
// which is exactly what experiment 3 measures. Do not "fix" this.

package work.rajc.booking.application.service;

import work.rajc.booking.application.port.in.BookSessionCommand;
import work.rajc.booking.application.port.in.BookSessionNaiveUseCase;
import work.rajc.booking.application.port.in.BookingConfirmation;
import work.rajc.booking.application.port.out.BookingStore;
import work.rajc.booking.domain.Booking;
import work.rajc.booking.domain.Charge;
import work.rajc.booking.domain.DepositAmount;

import java.util.UUID;

public final class BookSessionNaiveService implements BookSessionNaiveUseCase {

    private final BookingStore store;

    public BookSessionNaiveService(BookingStore store) {
        this.store = store;
    }

    @Override
    public BookingConfirmation book(BookSessionCommand command) {
        DepositAmount deposit = new DepositAmount(command.depositCents());
        UUID bookingId = UUID.randomUUID();
        UUID chargeId = UUID.randomUUID();
        store.inTransaction(tx -> {
            tx.addBooking(new Booking(bookingId, command.clientRef(), command.sessionId(),
                    command.dogId(), command.ownerId(), deposit));
            tx.addCharge(new Charge(chargeId, bookingId, command.clientRef(), deposit.cents()));
            return null;
        });
        return new BookingConfirmation(bookingId.toString(), chargeId.toString(), "confirmed");
    }
}
