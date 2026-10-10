// POST /naive/bookings: the control-group endpoint.
//
// INTENTIONALLY NAIVE BASELINE: no idempotency key, no deduplication, no retries,
// no locks. A retried request creates a second booking and a second charge, which
// is exactly what experiment 3 measures. Do not "fix" this.

using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Rajc.Bookings.Application.Ports.Inbound;

namespace Rajc.Bookings.Adapters.Inbound.Http;

public static class NaiveBookingEndpoints
{
    public static IEndpointRouteBuilder MapNaiveBookings(this IEndpointRouteBuilder routes)
    {
        routes.MapPost("/naive/bookings", async Task (HttpContext context, IBookSessionNaive useCase, FaultHook faultHook) =>
        {
            var booking = await ReadBookingAsync(context);
            if (booking is null)
            {
                return;
            }
            var confirmation = await useCase.BookAsync(ToCommand(booking));
            await faultHook.AfterCommitAsync(context.Request);
            context.Response.StatusCode = StatusCodes.Status201Created;
            await context.Response.WriteAsJsonAsync(new BookingResponse(confirmation.BookingId, confirmation.ChargeId, confirmation.Status), InvalidRequestHandling.StrictJson);
        });
        return routes;
    }

    internal static BookSessionCommand ToCommand(BookingRequest booking) =>
        new(booking.ClientRef, booking.SessionId, booking.DogId, booking.OwnerId, booking.DepositCents);

    /// <summary>Reads the strict JSON body; on any JSON error writes 400 invalid_request and returns null.</summary>
    internal static async Task<BookingRequest?> ReadBookingAsync(HttpContext context)
    {
        BookingRequest? booking;
        try
        {
            booking = await context.Request.ReadFromJsonAsync<BookingRequest>(InvalidRequestHandling.StrictJson);
        }
        catch (JsonException)
        {
            booking = null;
        }
        catch (BadHttpRequestException)
        {
            booking = null;
        }
        if (booking is null
            || string.IsNullOrEmpty(booking.ClientRef)
            || string.IsNullOrEmpty(booking.SessionId)
            || string.IsNullOrEmpty(booking.DogId)
            || string.IsNullOrEmpty(booking.OwnerId))
        {
            context.Response.StatusCode = StatusCodes.Status400BadRequest;
            await context.Response.WriteAsJsonAsync(new ErrorResponse("invalid_request"), InvalidRequestHandling.StrictJson);
            return null;
        }
        return booking;
    }
}
