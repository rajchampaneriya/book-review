using System;
using Rajc.Bookings.Domain;
using Xunit;

namespace Rajc.Bookings.Application.Tests;

public sealed class DepositAmountTests
{
    [Theory]
    [InlineData(1)]
    [InlineData(2500)]
    public void AcceptsPositiveCents(int cents)
    {
        Assert.Equal(cents, new DepositAmount(cents).Cents);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    [InlineData(-2500)]
    public void RejectsNonPositiveCents(int cents)
    {
        Assert.Throws<InvalidDepositException>(() => new DepositAmount(cents));
    }

    [Fact]
    public void BookingAndChargeAreImmutable()
    {
        var booking = new Booking(Guid.NewGuid(), "r1", "s-42", "d-7", "o-9", new DepositAmount(2500));
        var charge = new Charge(Guid.NewGuid(), booking.Id, "r1", 2500);

        var changedBooking = booking with { ClientRef = "x" };
        var changedCharge = charge with { AmountCents = 0 };

        Assert.NotEqual(booking, changedBooking);
        Assert.Equal("r1", booking.ClientRef); // the original is untouched
        Assert.NotEqual(charge, changedCharge);
        Assert.Equal(2500, charge.AmountCents);
    }
}
