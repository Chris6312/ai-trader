from app.services.historical import (
    BaselineModelArtifactRecord,
    BaselineModelHyperparameters,
    BaselineModelTrainingSummary,
    HistoricalBaselineModelService,
)


def test_historical_baseline_model_exports_are_available() -> None:
    assert BaselineModelHyperparameters is not None
    assert BaselineModelArtifactRecord is not None
    assert BaselineModelTrainingSummary is not None
    assert HistoricalBaselineModelService is not None
