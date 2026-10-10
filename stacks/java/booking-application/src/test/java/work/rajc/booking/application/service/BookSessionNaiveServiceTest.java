// The naive baseline: one transaction, no key, no deduplication. These tests
// assert the baseline behaves naively on purpose; a failure that says "two
// bookings for a retried request" is the expected result, not a bug.

package work.rajc.booking.application.service;

import work.rajc.booking.application.port.in.BookSessionCommand;
import work.rajc.booking.application.port.in.BookingConfirmation;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

class BookSessionNaiveServiceTest {

    private static BookSessionCommand command() {
        return new BookSessionCommand("r1", "s-42", "d-7", "o-9", 2500);
    }

    @Test
    void createsOneBookingAndOneChargeAndConfirms() {
        InMemoryBookingStore store = new InMemoryBookingStore();
        BookSessionNaiveService service = new BookSessionNaiveService(store);

        BookingConfirmation confirmation = service.book(command());

        assertEquals("confirmed", confirmation.status());
        assertEquals(1, store.bookings.size());
        assertEquals(1, store.charges.size());
        assertEquals(store.bookings.get(0).id().toString(), confirmation.bookingId());
        assertEquals(store.charges.get(0).id().toString(), confirmation.chargeId());
        assertEquals(2500, store.charges.get(0).amountCents());
    }

    @Test
    void aRetriedRequestCreatesASecondBookingAndCharge() {
        InMemoryBookingStore store = new InMemoryBookingStore();
        BookSessionNaiveService service = new BookSessionNaiveService(store);

        BookingConfirmation first = service.book(command());
        BookingConfirmation second = service.book(command());

        assertEquals(2, store.bookings.size());
        assertEquals(2, store.charges.size());
        assertNotEquals(first.bookingId(), second.bookingId());
        assertNotEquals(first.chargeId(), second.chargeId());
    }

    @Test
    void noIdempotencyKeysAreStored() {
        InMemoryBookingStore store = new InMemoryBookingStore();
        BookSessionNaiveService service = new BookSessionNaiveService(store);

        service.book(command());
        service.book(command());

        assertEquals(0, store.keys.size());
    }
}
