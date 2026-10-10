namespace Rajc.Bookings.Domain;

/// <summary>A positive amount of money in cents.</summary>
public sealed record DepositAmount
{
    public int Cents { get; }

    public DepositAmount(int cents)
    {
        if (cents <= 0)
        {
            throw new InvalidDepositException($"deposit_cents must be a positive integer, got {cents}");
        }
        Cents = cents;
    }
}
