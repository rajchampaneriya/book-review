// BookSessionIdempotentService: claim the key, book, store the result.
//
// G2 policy in one transaction: claim the idempotency key (unique), create the
// booking and the charge, store the result in the key row, commit. If the key
// is already claimed, roll back, then read the key row outside the failed
// transaction: a different hash is a Conflict, a stored result is a Replay, a
// claimed key with no result is InFlight (which should be impossible after a
// commit and is logged as a bug).

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading.Tasks;
using Rajc.Bookings.Application.Ports.Inbound;
using Rajc.Bookings.Application.Ports.Outbound;
using Rajc.Bookings.Domain;

namespace Rajc.Bookings.Application.Services;

public sealed class BookSessionIdempotentService : IBookSessionIdempotent
{
    private readonly IBookingStore _store;

    public BookSessionIdempotentService(IBookingStore store)
    {
        _store = store;
    }

    public async Task<BookingOutcome> BookAsync(string key, BookSessionCommand command)
    {
        var request = RequestHash.Compute(command);
        var deposit = new DepositAmount(command.DepositCents);
        var bookingId = Guid.NewGuid();
        var chargeId = Guid.NewGuid();
        var result = new Dictionary<string, string>
        {
            ["booking_id"] = bookingId.ToString(),
            ["charge_id"] = chargeId.ToString(),
            ["status"] = "confirmed",
        };
        try
        {
            await _store.RunInTransactionAsync(async tx =>
            {
                await tx.ClaimKeyAsync(key, request);
                await tx.AddBookingAsync(new Booking(bookingId, command.ClientRef, command.SessionId, command.DogId, command.OwnerId, deposit));
                await tx.AddChargeAsync(new Charge(chargeId, bookingId, command.ClientRef, deposit.Cents));
                await tx.StoreResultAsync(key, result);
            });
        }
        catch (KeyAlreadyClaimedException)
        {
            var stored = await _store.FindKeyAsync(key);
            if (stored is null || stored.RequestHash != request)
            {
                return new BookingOutcome.Conflict(key);
            }
            if (stored.Result is not null)
            {
                return new BookingOutcome.Replayed(
                    new BookingConfirmation(stored.Result["booking_id"], stored.Result["charge_id"], stored.Result["status"]));
            }
            Trace.WriteLine($"idempotency key {key} is claimed with no result after a commit; should be impossible (InFlight returned)");
            return new BookingOutcome.InFlight(key);
        }
        return new BookingOutcome.Created(new BookingConfirmation(result["booking_id"], result["charge_id"], result["status"]));
    }
}
