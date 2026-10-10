namespace Rajc.Bookings.Application.Ports.Inbound;

public sealed record BookSessionCommand(
    string ClientRef,
    string SessionId,
    string DogId,
    string OwnerId,
    int DepositCents);
