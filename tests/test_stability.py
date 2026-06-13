from app.weighing.stability import StabilityDetector


def test_window_not_full_is_not_stable() -> None:
    detector = StabilityDetector(window_size=3, threshold=0.005)

    assert detector.add_reading(0.520) is False
    assert detector.add_reading(0.521) is False


def test_full_window_with_small_variation_is_stable() -> None:
    detector = StabilityDetector(window_size=3, threshold=0.005)

    detector.add_reading(0.520)
    detector.add_reading(0.521)

    assert detector.add_reading(0.522) is True


def test_get_stable_value_returns_average() -> None:
    detector = StabilityDetector(window_size=3, threshold=0.005)
    detector.add_reading(0.520)
    detector.add_reading(0.521)
    detector.add_reading(0.522)

    assert round(detector.get_stable_value(), 3) == 0.521
