namespace Rajc.Bookings.Application.Ports.Inbound;

/// <summary>
/// The G2 policy in application terms: Created (this call booked), Replayed (an
/// earlier call with the same key and body booked), Conflict (same key,
/// different body) and InFlight (claimed but no result; a bug if seen).
/// HTTP status codes belong to the inbound adapter, not here.
/// </summary>
public abstract record BookingOutcome
{
    public sealed record Created(BookingConfirmation Confirmation) : BookingOutcome;

    public sealed record Replayed(BookingConfirmation Confirmation) : BookingOutcome;

    public sealed record Conflict(string Key) : BookingOutcome;

    public sealed record InFlight(string Key) : BookingOutcome;
}
