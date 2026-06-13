from app.pricing.transaction_service import TransactionService


def test_calculate_total_rounds_to_two_decimals() -> None:
    service = TransactionService()

    assert service.calculate_total(0.52, 12.8) == 6.66
