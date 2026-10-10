package work.rajc.booking.application.service;

import work.rajc.booking.application.port.in.BookSessionCommand;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

class RequestHashTest {

    // sha256 of "r1-000123\ns-42\nd-7\no-9\n2500" in lowercase hex
    private static final String EXPECTED = "cc482c9f1d2adbf0044c34f9b74ff7666a763290e0cd5297b65d8e558317f582";

    private static BookSessionCommand command(int depositCents) {
        return new BookSessionCommand("r1-000123", "s-42", "d-7", "o-9", depositCents);
    }

    @Test
    void knownVector() {
        assertEquals(EXPECTED, RequestHash.compute(command(2500)));
    }

    @Test
    void is64LowercaseHexChars() {
        String hash = RequestHash.compute(command(2500));
        assertEquals(64, hash.length());
        assertEquals(hash.toLowerCase(), hash);
    }

    @Test
    void everyFieldChangesTheHash() {
        String base = RequestHash.compute(command(2500));
        assertNotEquals(base, RequestHash.compute(command(2501)));
        assertNotEquals(base, RequestHash.compute(
                new BookSessionCommand("r1-000124", "s-42", "d-7", "o-9", 2500)));
        assertNotEquals(base, RequestHash.compute(
                new BookSessionCommand("r1-000123", "s-43", "d-7", "o-9", 2500)));
        assertNotEquals(base, RequestHash.compute(
                new BookSessionCommand("r1-000123", "s-42", "d-8", "o-9", 2500)));
        assertNotEquals(base, RequestHash.compute(
                new BookSessionCommand("r1-000123", "s-42", "d-7", "o-10", 2500)));
    }
}
