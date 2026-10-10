namespace Rajc.Bookings.Adapters.Inbound.Http;

public sealed record BookingResponse(
    string BookingId,
    string ChargeId,
    string Status);
