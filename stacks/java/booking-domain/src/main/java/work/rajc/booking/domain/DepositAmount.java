package work.rajc.booking.domain;

/** A positive amount of money in cents. */
public record DepositAmount(int cents) {

    public DepositAmount {
        if (cents <= 0) {
            throw new InvalidDepositException("deposit_cents must be a positive integer, got " + cents);
        }
    }
}
