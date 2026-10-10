using System;

namespace Rajc.Bookings.Domain;

public sealed record Booking(
    Guid Id,
    string ClientRef,
    string SessionId,
    string DogId,
    string OwnerId,
    DepositAmount Deposit);
