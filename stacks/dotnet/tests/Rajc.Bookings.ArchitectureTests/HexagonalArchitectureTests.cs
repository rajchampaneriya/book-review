// Hexagonal architecture rules for the .NET stack.
//
// Copy verbatim to tests/Rajc.Bookings.ArchitectureTests/HexagonalArchitectureTests.cs.
// tools/arch/check_hexagonal.py fails if the copy differs. The test project references every
// project under src/ and the packages NetArchTest.Rules and xunit (versions chosen at build time).

using System;
using System.Linq;
using System.Reflection;
using NetArchTest.Rules;
using Xunit;

namespace Rajc.Bookings.ArchitectureTests;

public sealed class HexagonalArchitectureTests
{
    private const string Domain = "Rajc.Bookings.Domain";
    private const string Application = "Rajc.Bookings.Application";
    private const string ApplicationServices = "Rajc.Bookings.Application.Services";
    private const string Adapters = "Rajc.Bookings.Adapters";
    private const string HttpAdapter = "Rajc.Bookings.Adapters.Inbound.Http";
    private const string PostgresAdapter = "Rajc.Bookings.Adapters.Outbound.Postgres";
    private const string Bootstrap = "Rajc.Bookings.Bootstrap";

    private static readonly string[] FrameworksAndDrivers =
    {
        "Microsoft.AspNetCore",
        "Microsoft.Extensions",
        "Npgsql",
        "System.Data",
        "System.Net",
        "System.Text.Json",
        "System.IO",
    };

    private static Types In(string assemblyName) => Types.InAssembly(Assembly.Load(assemblyName));

    [Fact]
    public void Domain_depends_on_no_other_layer() =>
        AssertKept(In(Domain).Should().NotHaveDependencyOnAny(Application, Adapters, Bootstrap).GetResult());

    [Fact]
    public void Domain_uses_no_frameworks_or_drivers() =>
        AssertKept(In(Domain).Should().NotHaveDependencyOnAny(FrameworksAndDrivers).GetResult());

    [Fact]
    public void Application_depends_only_on_domain() =>
        AssertKept(In(Application).Should().NotHaveDependencyOnAny(Adapters, Bootstrap).GetResult());

    [Fact]
    public void Application_uses_no_frameworks_or_drivers() =>
        AssertKept(In(Application).Should().NotHaveDependencyOnAny(FrameworksAndDrivers).GetResult());

    [Fact]
    public void Http_adapter_uses_ports_not_other_adapters_or_services() =>
        AssertKept(In(HttpAdapter).Should().NotHaveDependencyOnAny(PostgresAdapter, Bootstrap, ApplicationServices).GetResult());

    [Fact]
    public void Postgres_adapter_uses_ports_not_other_adapters_or_services() =>
        AssertKept(In(PostgresAdapter).Should().NotHaveDependencyOnAny(HttpAdapter, Bootstrap, ApplicationServices).GetResult());

    private static void AssertKept(TestResult result) =>
        Assert.True(
            result.IsSuccessful,
            "Architecture violations: " + string.Join(", ", result.FailingTypeNames ?? Enumerable.Empty<string>()));
}
