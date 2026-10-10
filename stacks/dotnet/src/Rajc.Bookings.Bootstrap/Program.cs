using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.Hosting;
using Rajc.Bookings.Adapters.Inbound.Http;
using Rajc.Bookings.Bootstrap;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddBookingServices(builder.Configuration);

var app = builder.Build();
app.UseExceptionHandler();

var stack = builder.Configuration["STACK"] ?? "dotnet";
app.MapHealthEndpoints(stack);
app.MapNaiveBookings();
app.MapBookings();

app.Run();
