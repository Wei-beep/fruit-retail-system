from app.camera.mock_camera import MockCamera
from app.db import repositories
from app.db.init_db import initialize_database
from app.pricing.price_service import PriceService
from app.pricing.transaction_service import TransactionService
from app.vision.mock_detector import MockFruitVegetableDetector
from app.weighing.mock_sensor import MockWeightSensor
from app.weighing.stability import StabilityDetector
from app.workflow.transaction_flow import TransactionFlow


def test_prepare_transaction_and_confirm_flow() -> None:
    initialize_database()
    before_count = len(repositories.list_transactions())
    flow = TransactionFlow(
        weight_sensor=MockWeightSensor(),
        stability_detector=StabilityDetector(window_size=10, threshold=0.005),
        camera=MockCamera("data/images/test", "data/images/captured"),
        detector=MockFruitVegetableDetector(),
        price_service=PriceService(),
        transaction_service=TransactionService(),
        poll_interval_seconds=0.0,
    )

    prepared = flow.prepare_transaction()

    assert prepared["label"] == "apple"
    assert prepared["name_cn"] == "苹果"
    assert prepared["total_price"] > 0
    assert len(repositories.list_transactions()) == before_count

    transaction_id = flow.confirm_transaction(prepared)

    assert transaction_id > 0
    assert len(repositories.list_transactions()) == before_count + 1
