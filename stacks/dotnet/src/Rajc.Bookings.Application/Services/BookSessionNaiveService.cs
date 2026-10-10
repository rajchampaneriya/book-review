// BookSessionNaiveService: the control group.
//
// INTENTIONALLY NAIVE BASELINE: no idempotency key, no deduplication, no retries,
// no locks, no unique constraints. One transaction: insert the booking, insert the
// charge, commit. A retried request creates a second booking and a second charge,
// which is exactly what experiment 3 measures. Do not "fix" this.

using System;
using System.Threading.Tasks;
using Rajc.Bookings.Application.Ports.Inbound;
using Rajc.Bookings.Application.Ports.Outbound;
using Rajc.Bookings.Domain;

namespace Rajc.Bookings.Application.Services;

public sealed class BookSessionNaiveService : IBookSessionNaive
{
    private readonly IBookingStore _store;

    public BookSessionNaiveService(IBookingStore store)
    {
        _store = store;
    }

    public async Task<BookingConfirmation> BookAsync(BookSessionCommand command)
    {
        var deposit = new DepositAmount(command.DepositCents);
        var bookingId = Guid.NewGuid();
        var chargeId = Guid.NewGuid();
        await _store.RunInTransactionAsync(async tx =>
        {
            await tx.AddBookingAsync(new Booking(bookingId, command.ClientRef, command.SessionId, command.DogId, command.OwnerId, deposit));
            await tx.AddChargeAsync(new Charge(chargeId, bookingId, command.ClientRef, deposit.Cents));
        });
        return new BookingConfirmation(bookingId.ToString(), chargeId.ToString(), "confirmed");
    }
}
