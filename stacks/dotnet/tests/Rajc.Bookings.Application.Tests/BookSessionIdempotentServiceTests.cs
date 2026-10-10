using System.Threading.Tasks;
using Rajc.Bookings.Application.Ports.Inbound;
using Rajc.Bookings.Application.Ports.Outbound;
using Rajc.Bookings.Application.Services;
using Xunit;

namespace Rajc.Bookings.Application.Tests;

public sealed class BookSessionIdempotentServiceTests
{
    private static BookSessionCommand Command(int depositCents = 2500) =>
        new("r1-000123", "s-42", "d-7", "o-9", depositCents);

    [Fact]
    public async Task FirstCallCreatesOneBookingAndOneCharge()
    {
        var store = new InMemoryBookingStore();
        var service = new BookSessionIdempotentService(store);

        var outcome = await service.BookAsync("k1", Command());

        var created = Assert.IsType<BookingOutcome.Created>(outcome);
        Assert.Equal("confirmed", created.Confirmation.Status);
        Assert.Single(store.Bookings);
        Assert.Single(store.Charges);
        Assert.NotNull(store.Keys["k1"].Result);
        Assert.Equal(RequestHash.Compute(Command()), store.Keys["k1"].RequestHash);
    }

    [Fact]
    public async Task SameKeyAndBodyReplaysWithoutNewWrites()
    {
        var store = new InMemoryBookingStore();
        var service = new BookSessionIdempotentService(store);

        var first = await service.BookAsync("k1", Command());
        var second = await service.BookAsync("k1", Command());

        Assert.IsType<BookingOutcome.Created>(first);
        var replayed = Assert.IsType<BookingOutcome.Replayed>(second);
        Assert.Equal(((BookingOutcome.Created)first).Confirmation, replayed.Confirmation);
        Assert.Single(store.Bookings);
        Assert.Single(store.Charges);
    }

    [Fact]
    public async Task SameKeyDifferentBodyIsAConflict()
    {
        var store = new InMemoryBookingStore();
        var service = new BookSessionIdempotentService(store);

        await service.BookAsync("k1", Command(2500));
        var outcome = await service.BookAsync("k1", Command(9999));

        Assert.IsType<BookingOutcome.Conflict>(outcome);
        Assert.Single(store.Bookings);
    }

    [Fact]
    public async Task ClaimedKeyWithoutResultIsInFlight()
    {
        var store = new InMemoryBookingStore();
        store.Keys["k1"] = new StoredKey("k1", RequestHash.Compute(Command()), null);
        var service = new BookSessionIdempotentService(store);

        var outcome = await service.BookAsync("k1", Command());

        Assert.IsType<BookingOutcome.InFlight>(outcome);
        Assert.Empty(store.Bookings);
    }

    [Fact]
    public async Task FailedTransactionLeavesNothingBehind()
    {
        var store = new InMemoryBookingStore();
        store.Keys["k1"] = new StoredKey("k1", RequestHash.Compute(Command()), null);
        var service = new BookSessionIdempotentService(store);

        await service.BookAsync("k1", Command());

        Assert.Empty(store.Bookings);
        Assert.Empty(store.Charges);
        Assert.Single(store.Keys);
    }
}
