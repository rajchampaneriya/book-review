package work.rajc.booking.application.port.out;

import java.util.Optional;
import java.util.function.Function;

public interface BookingStore {

    /** Reads a key row outside any failed transaction (the replay check). */
    Optional<StoredKey> findKey(String key);

    /** Runs one transaction: commit on clean exit, roll back on any error. */
    <T> T inTransaction(Function<BookingTransaction, T> work);
}
