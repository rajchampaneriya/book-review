using System;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Rajc.Bookings.Application.Ports.Inbound;

namespace Rajc.Bookings.Application.Services;

/// <summary>
/// The lowercase hex SHA-256 of the canonical request string (client_ref,
/// session_id, dog_id, owner_id and deposit_cents in decimal, joined by
/// newlines), exactly as docs/exp3-spec.md defines it.
/// </summary>
public static class RequestHash
{
    public static string Compute(BookSessionCommand command)
    {
        var canonical = string.Join(
            '\n',
            command.ClientRef,
            command.SessionId,
            command.DogId,
            command.OwnerId,
            command.DepositCents.ToString(CultureInfo.InvariantCulture));
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(canonical));
        return Convert.ToHexString(hash).ToLowerInvariant();
    }
}
