namespace Rajc.Bookings.Adapters.Inbound.Http;

/// <summary>Inbound DTO; unknown fields are rejected (rule G1).</summary>
public sealed record BookingRequest(
    string ClientRef,
    string SessionId,
    string DogId,
    string OwnerId,
    int DepositCents);
