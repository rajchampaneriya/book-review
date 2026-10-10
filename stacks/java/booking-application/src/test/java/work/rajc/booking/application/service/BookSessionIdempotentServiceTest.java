package work.rajc.booking.application.service;

import work.rajc.booking.application.port.in.BookSessionCommand;
import work.rajc.booking.application.port.in.BookingOutcome;
import work.rajc.booking.application.port.out.StoredKey;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNull;

class BookSessionIdempotentServiceTest {

    private static BookSessionCommand command(int depositCents) {
        return new BookSessionCommand("r1-000123", "s-42", "d-7", "o-9", depositCents);
    }

    @Test
    void firstCallCreatesOneBookingAndOneCharge() {
        InMemoryBookingStore store = new InMemoryBookingStore();
        BookSessionIdempotentService service = new BookSessionIdempotentService(store);

        BookingOutcome outcome = service.book("k1", command(2500));

        BookingOutcome.Created created = assertInstanceOf(BookingOutcome.Created.class, outcome);
        assertEquals("confirmed", created.confirmation().status());
        assertEquals(1, store.bookings.size());
        assertEquals(1, store.charges.size());
        assertEquals(RequestHash.compute(command(2500)), store.keys.get("k1").requestHash());
        assertEquals("confirmed", store.keys.get("k1").result().get("status"));
    }

    @Test
    void sameKeyAndBodyReplaysWithoutNewWrites() {
        InMemoryBookingStore store = new InMemoryBookingStore();
        BookSessionIdempotentService service = new BookSessionIdempotentService(store);

        BookingOutcome first = service.book("k1", command(2500));
        BookingOutcome second = service.book("k1", command(2500));

        assertInstanceOf(BookingOutcome.Created.class, first);
        BookingOutcome.Replayed replayed = assertInstanceOf(BookingOutcome.Replayed.class, second);
        assertEquals(((BookingOutcome.Created) first).confirmation(), replayed.confirmation());
        assertEquals(1, store.bookings.size());
        assertEquals(1, store.charges.size());
    }

    @Test
    void sameKeyDifferentBodyIsAConflict() {
        InMemoryBookingStore store = new InMemoryBookingStore();
        BookSessionIdempotentService service = new BookSessionIdempotentService(store);

        service.book("k1", command(2500));
        BookingOutcome outcome = service.book("k1", command(9999));

        assertInstanceOf(BookingOutcome.Conflict.class, outcome);
        assertEquals(1, store.bookings.size());
    }

    @Test
    void claimedKeyWithoutResultIsInFlight() {
        InMemoryBookingStore store = new InMemoryBookingStore();
        store.keys.put("k1", new StoredKey("k1", RequestHash.compute(command(2500)), null));
        BookSessionIdempotentService service = new BookSessionIdempotentService(store);

        BookingOutcome outcome = service.book("k1", command(2500));

        assertInstanceOf(BookingOutcome.InFlight.class, outcome);
        assertEquals(0, store.bookings.size());
    }

    @Test
    void failedTransactionLeavesNothingBehind() {
        InMemoryBookingStore store = new InMemoryBookingStore();
        store.keys.put("k1", new StoredKey("k1", RequestHash.compute(command(2500)), null));
        BookSessionIdempotentService service = new BookSessionIdempotentService(store);

        service.book("k1", command(2500));

        assertEquals(0, store.bookings.size());
        assertEquals(0, store.charges.size());
        assertEquals(1, store.keys.size());
        assertNull(store.keys.get("k1").result());
    }
}
