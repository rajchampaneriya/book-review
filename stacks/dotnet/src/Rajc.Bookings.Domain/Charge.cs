using System;

namespace Rajc.Bookings.Domain;

/// <summary>A simulated charge; there is no payment provider (rule G7).</summary>
public sealed record Charge(
    Guid Id,
    Guid BookingId,
    string ClientRef,
    int AmountCents);
