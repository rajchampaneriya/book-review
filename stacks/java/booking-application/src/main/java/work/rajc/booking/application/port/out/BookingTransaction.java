package work.rajc.booking.application.port.out;

import work.rajc.booking.domain.Booking;
import work.rajc.booking.domain.Charge;

import java.util.Map;

public interface BookingTransaction {

    /** Reserves the idempotency key; throws KeyAlreadyClaimedException if taken. */
    void claimKey(String key, String requestHash);

    void addBooking(Booking booking);

    void addCharge(Charge charge);

    void storeResult(String key, Map<String, String> result);
}
