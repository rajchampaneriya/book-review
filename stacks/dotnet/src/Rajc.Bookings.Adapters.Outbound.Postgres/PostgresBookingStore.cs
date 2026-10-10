using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Threading.Tasks;
using Npgsql;
using Rajc.Bookings.Application.Ports.Outbound;

namespace Rajc.Bookings.Adapters.Outbound.Postgres;

/// <summary>
/// Plain SQL over Npgsql, one transaction per use case (rule G3): the claim,
/// the booking, the charge and the result all commit or roll back together.
/// A unique violation (SQLSTATE 23505) is translated into the port's
/// KeyAlreadyClaimedException; no Npgsql exception crosses the port.
/// </summary>
public sealed class PostgresBookingStore : IBookingStore
{
    private readonly NpgsqlDataSource _dataSource;
    private readonly string _schema;

    public PostgresBookingStore(NpgsqlDataSource dataSource, string schema)
    {
        _dataSource = dataSource;
        _schema = schema;
    }

    public async Task<StoredKey?> FindKeyAsync(string key)
    {
        await using var connection = await _dataSource.OpenConnectionAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = $"SELECT key, request_hash, result FROM {_schema}.idempotency_keys WHERE key = $1";
        command.Parameters.AddWithValue(key);
        await using var reader = await command.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
        {
            return null;
        }
        Dictionary<string, string>? result = null;
        if (!reader.IsDBNull(2))
        {
            result = JsonSerializer.Deserialize<Dictionary<string, string>>(reader.GetString(2));
        }
        return new StoredKey(reader.GetString(0), reader.GetString(1), result);
    }

    public async Task RunInTransactionAsync(Func<IBookingTransaction, Task> work)
    {
        await using var connection = await _dataSource.OpenConnectionAsync();
        await using var transaction = await connection.BeginTransactionAsync();
        try
        {
            await work(new PostgresBookingTransaction(connection, _schema));
            await transaction.CommitAsync();
        }
        catch (PostgresException e) when (e.SqlState == "23505")
        {
            await transaction.RollbackAsync();
            throw new KeyAlreadyClaimedException(e.MessageText);
        }
        // an uncommitted transaction rolls back when the connection disposes
    }
}
