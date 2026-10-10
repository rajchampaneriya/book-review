package work.rajc.booking.domain;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

class DepositAmountTest {

    @ParameterizedTest
    @ValueSource(ints = {1, 2500})
    void acceptsPositiveCents(int cents) {
        assertEquals(cents, new DepositAmount(cents).cents());
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1, -2500})
    void rejectsNonPositiveCents(int cents) {
        org.junit.jupiter.api.Assertions.assertThrows(
                InvalidDepositException.class, () -> new DepositAmount(cents));
    }

    @Test
    void bookingAndChargeAreImmutable() {
        Booking booking = new Booking(UUID.randomUUID(), "r1", "s-42", "d-7", "o-9", new DepositAmount(2500));
        Booking other = new Booking(booking.id(), "r1", "s-42", "d-7", "o-9", new DepositAmount(2501));
        Charge charge = new Charge(UUID.randomUUID(), booking.id(), "r1", 2500);

        assertNotEquals(booking, other); // a copied booking with a different deposit is a new value
        assertEquals(2500, charge.amountCents()); // records expose no setters: values never change in place
    }
}
