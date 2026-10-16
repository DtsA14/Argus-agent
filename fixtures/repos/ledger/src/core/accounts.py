"""Accounts and the payment terms that apply to them."""
from dataclasses import dataclass

from ..common.options import merge_options
from ..common.settings import base_terms, schedule_terms
from .terms import terms_from


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    schedule: str = "standard"


def account_terms(account):
    """The payment terms of an account: the base terms with its schedule's settings applied."""
    return terms_from(merge_options(base_terms(), schedule_terms(account.schedule)))
