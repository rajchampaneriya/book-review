using System.Threading.Tasks;

namespace Rajc.Bookings.Application.Ports.Inbound;

public interface IBookSessionIdempotent
{
    Task<BookingOutcome> BookAsync(string key, BookSessionCommand command);
}
