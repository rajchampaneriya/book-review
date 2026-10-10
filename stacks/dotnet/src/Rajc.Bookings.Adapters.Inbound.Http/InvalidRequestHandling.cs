using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Http;
using Rajc.Bookings.Domain;

namespace Rajc.Bookings.Adapters.Inbound.Http;

/// <summary>
/// Strict JSON for the inbound DTOs: unknown fields rejected, no number
/// coercion. Endpoints read the body with these options and map any JSON
/// error to 400 {"error":"invalid_request"}; the exception handler covers the
/// invalid-deposit case raised by the domain.
/// </summary>
public static class InvalidRequestHandling
{
    public static readonly JsonSerializerOptions StrictJson = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    };
}

public sealed class InvalidRequestExceptionHandler : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(HttpContext httpContext, System.Exception exception, System.Threading.CancellationToken cancellationToken)
    {
        if (exception is not (JsonException or BadHttpRequestException or InvalidDepositException))
        {
            return false;
        }
        httpContext.Response.StatusCode = StatusCodes.Status400BadRequest;
        await httpContext.Response.WriteAsJsonAsync(new ErrorResponse("invalid_request"), cancellationToken);
        return true;
    }
}
