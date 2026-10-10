// The naive baseline: one transaction, no key, no deduplication. These tests
// assert the baseline behaves naively on purpose; a failure that says "two
// bookings for a retried request" is the expected result, not a bug.

using System.Linq;
using System.Threading.Tasks;
using Rajc.Bookings.Application.Ports.Inbound;
using Rajc.Bookings.Application.Ports.Outbound;
using Rajc.Bookings.Application.Services;
using Xunit;

namespace Rajc.Bookings.Application.Tests;

public sealed class BookSessionNaiveServiceTests
{
    private static BookSessionCommand Command(string clientRef = "r1") =>
        new(clientRef, "s-42", "d-7", "o-9", 2500);

    [Fact]
    public async Task CreatesOneBookingAndOneChargeAndConfirms()
    {
        var store = new InMemoryBookingStore();
        var service = new BookSessionNaiveService(store);

        var confirmation = await service.BookAsync(Command());

        Assert.Equal("confirmed", confirmation.Status);
        Assert.Single(store.Bookings);
        Assert.Single(store.Charges);
        Assert.Equal(store.Bookings[0].Id.ToString(), confirmation.BookingId);
        Assert.Equal(store.Charges[0].Id.ToString(), confirmation.ChargeId);
        Assert.Equal(2500, store.Charges[0].AmountCents);
    }

    [Fact]
    public async Task ARetriedRequestCreatesASecondBookingAndCharge()
    {
        var store = new InMemoryBookingStore();
        var service = new BookSessionNaiveService(store);

        var first = await service.BookAsync(Command());
        var second = await service.BookAsync(Command());

        Assert.Equal(2, store.Bookings.Count);
        Assert.Equal(2, store.Charges.Count);
        Assert.NotEqual(first.BookingId, second.BookingId);
        Assert.NotEqual(first.ChargeId, second.ChargeId);
        Assert.Equal(2, store.Bookings.Select(b => b.Id).ToHashSet().Count);
    }

    [Fact]
    public async Task NoIdempotencyKeysAreStored()
    {
        var store = new InMemoryBookingStore();
        var service = new BookSessionNaiveService(store);

        await service.BookAsync(Command());
        await service.BookAsync(Command());

        Assert.Empty(store.Keys);
    }
}
