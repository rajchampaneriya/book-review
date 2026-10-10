using System;
using System.Threading.Tasks;

namespace Rajc.Bookings.Application.Ports.Outbound;

public interface IBookingStore
{
    /// <summary>Read a key row outside any failed transaction (the replay check).</summary>
    Task<StoredKey?> FindKeyAsync(string key);

    /// <summary>Run one transaction: commit on clean exit, roll back on any error.</summary>
    Task RunInTransactionAsync(Func<IBookingTransaction, Task> work);
}
