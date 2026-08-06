from backend.controllers.ap_controller import APController
from domain.ap_lifecycle import APValidationError


def test_worker_error_uses_exception_message_not_traceback():
    message = "Allocation exceeds the open balance of invoice 26-0066."

    assert APController._error_text(
        (APValidationError, APValidationError(message), "Traceback (most recent call last): ...")
    ) == message


def test_direct_error_message_is_preserved():
    assert APController._error_text(APValidationError("A/P bill was not found.")) == "A/P bill was not found."
