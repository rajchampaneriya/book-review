using System;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Rajc.Bookings.Adapters.Inbound.Http;
using Rajc.Bookings.Adapters.Outbound.Postgres;
using Rajc.Bookings.Application.Ports.Inbound;
using Rajc.Bookings.Application.Ports.Outbound;
using Rajc.Bookings.Application.Services;

namespace Rajc.Bookings.Bootstrap;

/// <summary>Composition root: wires the services to the ports and the adapters.</summary>
public static class ServiceRegistration
{
    public static IServiceCollection AddBookingServices(this IServiceCollection services, IConfiguration configuration)
    {
        var databaseUrl = configuration["DATABASE_URL"] ?? "postgresql://wcf:wcf-local@localhost:5432/bookings";
        var schema = configuration["DB_SCHEMA"] ?? "dotnet";
        var dataSourceBuilder = new NpgsqlDataSourceBuilder(ToKeywordConnectionString(databaseUrl));
        dataSourceBuilder.ConnectionStringBuilder.MaxPoolSize = 20; // spec: 20 connections per service
        var dataSource = dataSourceBuilder.Build();

        services.AddSingleton(dataSource);
        services.AddSingleton<IBookingStore>(sp => new PostgresBookingStore(sp.GetRequiredService<NpgsqlDataSource>(), schema));
        services.AddSingleton<IBookSessionNaive, BookSessionNaiveService>();
        services.AddSingleton<IBookSessionIdempotent, BookSessionIdempotentService>();
        services.AddSingleton(new FaultHook(
            enabled: configuration["FAULT_INJECTION"] == "enabled",
            holdMs: int.TryParse(configuration["FAULT_HOLD_MS"], out var ms) ? ms : 2000));

        services.AddSingleton<IExceptionHandler, InvalidRequestExceptionHandler>();
        services.AddProblemDetails();
        services.ConfigureHttpJsonOptions(options =>
        {
            options.SerializerOptions.UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow;
        });
        return services;
    }

    // Npgsql 10's NpgsqlConnectionStringBuilder rejects URI-style connection
    // strings, so the standard DATABASE_URL is translated into keywords.
    private static string ToKeywordConnectionString(string databaseUrl)
    {
        if (!databaseUrl.StartsWith("postgresql://", StringComparison.OrdinalIgnoreCase)
            && !databaseUrl.StartsWith("postgres://", StringComparison.OrdinalIgnoreCase))
        {
            return databaseUrl;
        }
        var uri = new Uri(databaseUrl);
        var userInfo = uri.UserInfo.Split(':', 2);
        var password = userInfo.Length > 1 ? Uri.UnescapeDataString(userInfo[1]) : string.Empty;
        return $"Host={uri.Host};Port={uri.Port};Username={Uri.UnescapeDataString(userInfo[0])};"
            + $"Password={password};Database={uri.AbsolutePath.Trim('/')}";
    }
}
