using System.Threading.Tasks;

namespace Rajc.Bookings.Application.Ports.Inbound;

public interface IBookSessionNaive
{
    Task<BookingConfirmation> BookAsync(BookSessionCommand command);
}
