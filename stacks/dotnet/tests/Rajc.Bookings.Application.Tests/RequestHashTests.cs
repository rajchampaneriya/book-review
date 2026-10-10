using System.Linq;
using Rajc.Bookings.Application.Ports.Inbound;
using Rajc.Bookings.Application.Services;
using Xunit;

namespace Rajc.Bookings.Application.Tests;

public sealed class RequestHashTests
{
    // sha256 of "r1-000123\ns-42\nd-7\no-9\n2500" in lowercase hex
    private const string Expected = "cc482c9f1d2adbf0044c34f9b74ff7666a763290e0cd5297b65d8e558317f582";

    private static BookSessionCommand Command(int depositCents = 2500) =>
        new("r1-000123", "s-42", "d-7", "o-9", depositCents);

    [Fact]
    public void KnownVector()
    {
        Assert.Equal(Expected, RequestHash.Compute(Command()));
    }

    [Fact]
    public void Is64LowercaseHexChars()
    {
        var hash = RequestHash.Compute(Command());
        Assert.Equal(64, hash.Length);
        Assert.Equal(hash.ToLowerInvariant(), hash);
    }

    [Fact]
    public void EveryFieldChangesTheHash()
    {
        var baseHash = RequestHash.Compute(Command());
        var variants = new[]
        {
            RequestHash.Compute(Command(2501)),
            RequestHash.Compute(new BookSessionCommand("r1-000124", "s-42", "d-7", "o-9", 2500)),
            RequestHash.Compute(new BookSessionCommand("r1-000123", "s-43", "d-7", "o-9", 2500)),
            RequestHash.Compute(new BookSessionCommand("r1-000123", "s-42", "d-8", "o-9", 2500)),
            RequestHash.Compute(new BookSessionCommand("r1-000123", "s-42", "d-7", "o-10", 2500)),
        };
        Assert.Equal(6, new[] { baseHash }.Concat(variants).ToHashSet().Count);
    }
}
