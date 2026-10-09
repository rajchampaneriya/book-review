import dataclasses
import uuid

import pytest

from booking.domain.booking import Booking, Charge, DepositAmount
from booking.domain.errors import InvalidDepositError


def test_deposit_amount_accepts_positive_cents():
    assert DepositAmount(1).cents == 1
    assert DepositAmount(2500).cents == 2500


@pytest.mark.parametrize("bad", [0, -1, -2500])
def test_deposit_amount_rejects_non_positive_cents(bad):
    with pytest.raises(InvalidDepositError):
        DepositAmount(bad)


@pytest.mark.parametrize("bad", [None, "2500", 25.0, True])
def test_deposit_amount_rejects_non_integers(bad):
    with pytest.raises(InvalidDepositError):
        DepositAmount(bad)


def test_booking_and_charge_are_immutable():
    booking = Booking(uuid.uuid4(), "r1", "s-42", "d-7", "o-9", DepositAmount(2500))
    charge = Charge(uuid.uuid4(), booking.id, "r1", 2500)
    with pytest.raises(dataclasses.FrozenInstanceError):
        booking.client_ref = "x"
    with pytest.raises(dataclasses.FrozenInstanceError):
        charge.amount_cents = 0
