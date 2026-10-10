using System;

namespace Rajc.Bookings.Application.Ports.Outbound;

/// <summary>
/// The idempotency key is already claimed; the attempted transaction was
/// rolled back. The Postgres adapter translates SQLSTATE 23505 into this;
/// no driver exception crosses the port.
/// </summary>
public sealed class KeyAlreadyClaimedException : Exception
{
    public KeyAlreadyClaimedException(string message) : base(message)
    {
    }
}
