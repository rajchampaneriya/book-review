// BookSessionIdempotentService: claim the key, book, store the result.
//
// G2 policy in one transaction: claim the idempotency key (unique), create the
// booking and the charge, store the result in the key row, commit. If the key
// is already claimed, roll back, then read the key row outside the failed
// transaction: a different hash is a Conflict, a stored result is a Replay, a
// claimed key with no result is InFlight (which should be impossible after a
// commit and is logged as a bug).

package work.rajc.booking.application.service;

import work.rajc.booking.application.port.in.BookSessionCommand;
import work.rajc.booking.application.port.in.BookSessionIdempotentUseCase;
import work.rajc.booking.application.port.in.BookingConfirmation;
import work.rajc.booking.application.port.in.BookingOutcome;
import work.rajc.booking.application.port.out.BookingStore;
import work.rajc.booking.application.port.out.KeyAlreadyClaimedException;
import work.rajc.booking.application.port.out.StoredKey;
import work.rajc.booking.domain.Booking;
import work.rajc.booking.domain.Charge;
import work.rajc.booking.domain.DepositAmount;

import java.util.Map;
import java.util.UUID;
import java.util.logging.Logger;

public final class BookSessionIdempotentService implements BookSessionIdempotentUseCase {

    private static final Logger LOG = Logger.getLogger(BookSessionIdempotentService.class.getName());

    private final BookingStore store;

    public BookSessionIdempotentService(BookingStore store) {
        this.store = store;
    }

    @Override
    public BookingOutcome book(String key, BookSessionCommand command) {
        String request = RequestHash.compute(command);
        DepositAmount deposit = new DepositAmount(command.depositCents());
        UUID bookingId = UUID.randomUUID();
        UUID chargeId = UUID.randomUUID();
        Map<String, String> result = Map.of(
                "booking_id", bookingId.toString(),
                "charge_id", chargeId.toString(),
                "status", "confirmed");
        try {
            store.inTransaction(tx -> {
                tx.claimKey(key, request);
                tx.addBooking(new Booking(bookingId, command.clientRef(), command.sessionId(),
                        command.dogId(), command.ownerId(), deposit));
                tx.addCharge(new Charge(chargeId, bookingId, command.clientRef(), deposit.cents()));
                tx.storeResult(key, result);
                return null;
            });
        } catch (KeyAlreadyClaimedException e) {
            StoredKey stored = store.findKey(key).orElse(null);
            if (stored == null || !stored.requestHash().equals(request)) {
                return new BookingOutcome.Conflict(key);
            }
            if (stored.result() != null) {
                return new BookingOutcome.Replayed(new BookingConfirmation(
                        stored.result().get("booking_id"),
                        stored.result().get("charge_id"),
                        stored.result().get("status")));
            }
            LOG.severe(() -> "idempotency key " + key
                    + " is claimed with no result after a commit; should be impossible (InFlight returned)");
            return new BookingOutcome.InFlight(key);
        }
        return new BookingOutcome.Created(new BookingConfirmation(
                result.get("booking_id"), result.get("charge_id"), result.get("status")));
    }
}
