from aigc import __version__
from aigc.enforcement import enforce_invocation
from aigc.errors import InvocationValidationError


def test_public_api_imports():
    assert callable(enforce_invocation)
    assert __version__ == "0.1.1"
    assert InvocationValidationError.__name__ == "InvocationValidationError"
