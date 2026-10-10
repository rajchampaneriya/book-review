using System.Collections.Generic;
using System.Text.Json;
using System.Threading.Tasks;
using Npgsql;
using Rajc.Bookings.Application.Ports.Outbound;
using Rajc.Bookings.Domain;

namespace Rajc.Bookings.Adapters.Outbound.Postgres;

public sealed class PostgresBookingTransaction : IBookingTransaction
{
    private readonly NpgsqlConnection _connection;
    private readonly string _schema;

    public PostgresBookingTransaction(NpgsqlConnection connection, string schema)
    {
        _connection = connection;
        _schema = schema;
    }

    public Task ClaimKeyAsync(string key, string requestHash) =>
        Execute($"INSERT INTO {_schema}.idempotency_keys (key, request_hash) VALUES ($1, $2)", key, requestHash);

    public Task AddBookingAsync(Booking booking) =>
        Execute(
            $"INSERT INTO {_schema}.bookings (id, client_ref, session_id, dog_id, owner_id, deposit_cents) VALUES ($1, $2, $3, $4, $5, $6)",
            booking.Id, booking.ClientRef, booking.SessionId, booking.DogId, booking.OwnerId, booking.Deposit.Cents);

    public Task AddChargeAsync(Charge charge) =>
        Execute(
            $"INSERT INTO {_schema}.charges (id, booking_id, client_ref, amount_cents) VALUES ($1, $2, $3, $4)",
            charge.Id, charge.BookingId, charge.ClientRef, charge.AmountCents);

    public Task StoreResultAsync(string key, Dictionary<string, string> result) =>
        Execute($"UPDATE {_schema}.idempotency_keys SET result = $2::jsonb WHERE key = $1", key, JsonSerializer.Serialize(result));

    private async Task Execute(params object?[] values)
    {
        await using var command = _connection.CreateCommand();
        command.CommandText = (string)values[0]!;
        for (var i = 1; i < values.Length; i++)
        {
            command.Parameters.AddWithValue(values[i]);
        }
        await command.ExecuteNonQueryAsync();
    }
}
