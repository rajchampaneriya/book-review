"""Domain errors."""


class InvalidDepositError(ValueError):
    """A deposit amount must be a positive integer number of cents."""
