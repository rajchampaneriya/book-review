package work.rajc.booking.domain;

/** A deposit amount must be a positive integer number of cents. */
public class InvalidDepositException extends IllegalArgumentException {

    public InvalidDepositException(String message) {
        super(message);
    }
}
