package work.rajc.booking.application.service;

import work.rajc.booking.application.port.out.BookingStore;
import work.rajc.booking.application.port.out.BookingTransaction;
import work.rajc.booking.application.port.out.KeyAlreadyClaimedException;
import work.rajc.booking.application.port.out.StoredKey;
import work.rajc.booking.domain.Booking;
import work.rajc.booking.domain.Charge;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;

/**
 * An in-memory BookingStore for unit tests. Mirrors the Postgres adapter's
 * semantics: the key claim is unique, the result is written in the same
 * transaction, and a failed transaction leaves nothing behind (the pending
 * writes are only merged into the store on a clean exit).
 */
final class InMemoryBookingStore implements BookingStore {

    final Map<String, StoredKey> keys = new HashMap<>();
    final List<Booking> bookings = new ArrayList<>();
    final List<Charge> charges = new ArrayList<>();

    @Override
    public Optional<StoredKey> findKey(String key) {
        return Optional.ofNullable(keys.get(key));
    }

    @Override
    public <T> T inTransaction(Function<BookingTransaction, T> work) {
        InMemoryTransaction tx = new InMemoryTransaction(this);
        T result = work.apply(tx); // KeyAlreadyClaimedException aborts: nothing is merged
        tx.commit();
        return result;
    }

    private static final class InMemoryTransaction implements BookingTransaction {

        private final InMemoryBookingStore store;
        private final Map<String, StoredKey> keys = new HashMap<>();
        private final List<Booking> bookings = new ArrayList<>();
        private final List<Charge> charges = new ArrayList<>();

        InMemoryTransaction(InMemoryBookingStore store) {
            this.store = store;
        }

        @Override
        public void claimKey(String key, String requestHash) {
            if (store.keys.containsKey(key) || keys.containsKey(key)) {
                throw new KeyAlreadyClaimedException(key);
            }
            keys.put(key, new StoredKey(key, requestHash, null));
        }

        @Override
        public void addBooking(Booking booking) {
            bookings.add(booking);
        }

        @Override
        public void addCharge(Charge charge) {
            charges.add(charge);
        }

        @Override
        public void storeResult(String key, Map<String, String> result) {
            StoredKey stored = keys.get(key);
            keys.put(key, new StoredKey(stored.key(), stored.requestHash(), Map.copyOf(result)));
        }

        void commit() {
            store.keys.putAll(keys);
            store.bookings.addAll(bookings);
            store.charges.addAll(charges);
        }
    }
}
