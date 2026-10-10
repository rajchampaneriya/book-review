using System.Threading.Tasks;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;

namespace Rajc.Bookings.Adapters.Inbound.Http;

public static class HealthEndpoints
{
    public static IEndpointRouteBuilder MapHealthEndpoints(this IEndpointRouteBuilder routes, string stack)
    {
        routes.MapGet("/health", () => Results.Json(new { status = "ok", stack }));
        return routes;
    }
}
