using System.Collections.Generic;
using System.Threading.Tasks;
using Rajc.Bookings.Domain;

namespace Rajc.Bookings.Application.Ports.Outbound;

public interface IBookingTransaction
{
    /// <summary>Reserve the idempotency key; throws KeyAlreadyClaimedException if taken.</summary>
    Task ClaimKeyAsync(string key, string requestHash);

    Task AddBookingAsync(Booking booking);

    Task AddChargeAsync(Charge charge);

    Task StoreResultAsync(string key, Dictionary<string, string> result);
}
