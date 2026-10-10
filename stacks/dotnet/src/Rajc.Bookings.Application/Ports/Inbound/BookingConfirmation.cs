namespace Rajc.Bookings.Application.Ports.Inbound;

public sealed record BookingConfirmation(
    string BookingId,
    string ChargeId,
    string Status);
