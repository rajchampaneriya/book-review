using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Rajc.Bookings.Application.Ports.Outbound;
using Rajc.Bookings.Domain;

namespace Rajc.Bookings.Application.Tests;

/// <summary>
/// An in-memory BookingStore for unit tests. Mirrors the Postgres adapter's
/// semantics: the key claim is unique, the result is written in the same
/// transaction, and a failed transaction leaves nothing behind (the pending
/// writes are only merged into the store on a clean exit).
/// </summary>
public sealed class InMemoryBookingStore : IBookingStore
{
    public Dictionary<string, StoredKey> Keys { get; } = new();

    public List<Booking> Bookings { get; } = new();

    public List<Charge> Charges { get; } = new();

    public Task<StoredKey?> FindKeyAsync(string key)
    {
        return Task.FromResult(Keys.TryGetValue(key, out var stored) ? stored : null);
    }

    public async Task RunInTransactionAsync(Func<IBookingTransaction, Task> work)
    {
        var tx = new InMemoryTransaction(this);
        await work(tx); // KeyAlreadyClaimedException aborts: nothing is merged
        tx.Commit();
    }

    private sealed class InMemoryTransaction : IBookingTransaction
    {
        private readonly InMemoryBookingStore _store;
        private readonly Dictionary<string, StoredKey> _keys = new();
        private readonly List<Booking> _bookings = new();
        private readonly List<Charge> _charges = new();

        public InMemoryTransaction(InMemoryBookingStore store)
        {
            _store = store;
        }

        public Task ClaimKeyAsync(string key, string requestHash)
        {
            if (_store.Keys.ContainsKey(key) || _keys.ContainsKey(key))
            {
                throw new KeyAlreadyClaimedException(key);
            }
            _keys[key] = new StoredKey(key, requestHash, null);
            return Task.CompletedTask;
        }

        public Task AddBookingAsync(Booking booking)
        {
            _bookings.Add(booking);
            return Task.CompletedTask;
        }

        public Task AddChargeAsync(Charge charge)
        {
            _charges.Add(charge);
            return Task.CompletedTask;
        }

        public Task StoreResultAsync(string key, Dictionary<string, string> result)
        {
            _keys[key] = new StoredKey(key, _keys[key].RequestHash, new Dictionary<string, string>(result));
            return Task.CompletedTask;
        }

        public void Commit()
        {
            foreach (var (key, stored) in _keys)
            {
                _store.Keys[key] = stored;
            }
            _store.Bookings.AddRange(_bookings);
            _store.Charges.AddRange(_charges);
        }
    }
}
