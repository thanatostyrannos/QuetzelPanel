"""Tenancy domain models."""
from __future__ import annotations

from pydantic import BaseModel


class Customer(BaseModel):
    id: str
    name: str
