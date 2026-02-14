import pytest
from src.validator import validate_preconditions
from src.errors import PreconditionError

def test_precondition_missing():
    with pytest.raises(PreconditionError):
        validate_preconditions({}, {"pre_conditions": {"required": ["role_declared"]}})
