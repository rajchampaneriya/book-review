# Four stages: build, unit, arch, runtime (docs/exp3-spec.md, Infrastructure).
FROM mcr.microsoft.com/dotnet/sdk:10.0.401 AS build
ENV DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
WORKDIR /src
COPY . .
RUN dotnet restore Rajc.Bookings.slnx \
    && dotnet publish src/Rajc.Bookings.Bootstrap -c Release -o /publish --no-restore

FROM mcr.microsoft.com/dotnet/sdk:10.0.401 AS unit
ENV DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
WORKDIR /src
COPY --from=build /src .
RUN dotnet test tests/Rajc.Bookings.Application.Tests --no-restore

FROM mcr.microsoft.com/dotnet/sdk:10.0.401 AS arch
ENV DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1
WORKDIR /src
COPY --from=build /src .
RUN dotnet test tests/Rajc.Bookings.ArchitectureTests --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /publish .
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "Rajc.Bookings.Bootstrap.dll"]
