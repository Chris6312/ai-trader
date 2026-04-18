from app.services.historical import (
    HistoricalLabelGenerationSummary,
    HistoricalLabelGeneratorService,
    HistoricalLabelPolicy,
    HistoricalReplayLabelRecord,
    LabelPolicyVersionRecord,
)


def test_historical_label_generator_exports_are_available() -> None:
    assert HistoricalLabelGeneratorService is not None
    assert HistoricalLabelPolicy is not None
    assert HistoricalReplayLabelRecord is not None
    assert HistoricalLabelGenerationSummary is not None
    assert LabelPolicyVersionRecord is not None
