using System;

namespace Rajc.Bookings.Domain;

/// <summary>A deposit amount must be a positive integer number of cents.</summary>
public sealed class InvalidDepositException : ArgumentException
{
    public InvalidDepositException(string message) : base(message)
    {
    }
}
