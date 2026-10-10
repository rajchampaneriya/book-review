using System.Collections.Generic;

namespace Rajc.Bookings.Application.Ports.Outbound;

public sealed record StoredKey(
    string Key,
    string RequestHash,
    Dictionary<string, string>? Result);
