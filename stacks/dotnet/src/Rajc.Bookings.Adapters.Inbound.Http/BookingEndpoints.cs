// POST /v2/bookings: the idempotency-keyed endpoint. The route validates the
// Idempotency-Key header, calls the driving port, maps the outcome to a status
// code (Created/Replayed 201, Conflict 422, InFlight 409) and then runs the
// fault hook. All policy lives in the application layer; only transport here.

using System.Threading.Tasks;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Rajc.Bookings.Application.Ports.Inbound;

namespace Rajc.Bookings.Adapters.Inbound.Http;

public static class BookingEndpoints
{
    private const string KeyHeader = "Idempotency-Key";

    public static IEndpointRouteBuilder MapBookings(this IEndpointRouteBuilder routes)
    {
        routes.MapPost("/v2/bookings", async Task (HttpContext context, IBookSessionIdempotent useCase, FaultHook faultHook) =>
        {
            if (!TryGetValidKey(context.Request, out var key))
            {
                context.Response.StatusCode = StatusCodes.Status400BadRequest;
                await context.Response.WriteAsJsonAsync(new ErrorResponse("idempotency_key_required"), InvalidRequestHandling.StrictJson);
                return;
            }
            var booking = await NaiveBookingEndpoints.ReadBookingAsync(context);
            if (booking is null)
            {
                return;
            }
            var outcome = await useCase.BookAsync(key, NaiveBookingEndpoints.ToCommand(booking));
            await faultHook.AfterCommitAsync(context.Request);

            switch (outcome)
            {
                case BookingOutcome.Conflict:
                    context.Response.StatusCode = StatusCodes.Status422UnprocessableEntity;
                    await context.Response.WriteAsJsonAsync(new ErrorResponse("idempotency_conflict"), InvalidRequestHandling.StrictJson);
                    return;
                case BookingOutcome.InFlight:
                    context.Response.StatusCode = StatusCodes.Status409Conflict;
                    context.Response.Headers["Retry-After"] = "1";
                    await context.Response.WriteAsJsonAsync(new ErrorResponse("idempotency_in_flight"), InvalidRequestHandling.StrictJson);
                    return;
            }

            context.Response.StatusCode = StatusCodes.Status201Created;
            var confirmation = outcome switch
            {
                BookingOutcome.Created created => created.Confirmation,
                BookingOutcome.Replayed replayed => replayed.Confirmation,
                _ => throw new System.InvalidOperationException($"unreachable outcome {outcome.GetType().Name}"),
            };
            if (outcome is BookingOutcome.Replayed)
            {
                context.Response.Headers["Idempotent-Replayed"] = "true";
            }
            await context.Response.WriteAsJsonAsync(new BookingResponse(confirmation.BookingId, confirmation.ChargeId, confirmation.Status), InvalidRequestHandling.StrictJson);
        });
        return routes;
    }

    private static bool TryGetValidKey(HttpRequest request, out string key)
    {
        key = request.Headers[KeyHeader].ToString();
        if (key.Length < 1 || key.Length > 255)
        {
            return false;
        }
        foreach (var c in key)
        {
            if (c < '!' || c > '~')
            {
                return false;
            }
        }
        return true;
    }
}
