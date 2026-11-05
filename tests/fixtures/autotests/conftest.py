"""Fixture code for review-autotest scenarios; excluded from pytest collection."""

import pytest


@pytest.fixture
def authorized_agent():
    """Provide a user authorized for the LADA quote flow."""
    return {"role": "Агент", "brand": "LADA"}
