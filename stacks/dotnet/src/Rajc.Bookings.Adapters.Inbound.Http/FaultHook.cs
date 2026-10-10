using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;

namespace Rajc.Bookings.Adapters.Inbound.Http;

/// <summary>
/// The fault hook: a transport concern living in the inbound HTTP adapter.
/// Called after the use case has returned (the commit has happened) and
/// before the response is written; a no-op unless enabled and the request
/// carries X-Fault: hold-after-commit, then holds the response so the client
/// times out on a booking that is already committed.
/// </summary>
public sealed class FaultHook
{
    private readonly bool _enabled;
    private readonly int _holdMs;

    public FaultHook(bool enabled, int holdMs)
    {
        _enabled = enabled;
        _holdMs = holdMs;
    }

    public async Task AfterCommitAsync(HttpRequest request)
    {
        if (_enabled && request.Headers.TryGetValue("X-Fault", out var value) && value.ToString() == "hold-after-commit")
        {
            await Task.Delay(_holdMs);
        }
    }
}
