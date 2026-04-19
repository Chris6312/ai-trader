from app.services.historical.backfill_planner import BackfillPlanner
from app.services.historical.ai_scheduler import AIResearchSchedulerService
from app.services.historical.feature_builder import FeatureBuilderService
from app.services.historical.historical_strategy_replay import HistoricalStrategyReplayService
from app.services.historical.historical_label_generator import HistoricalLabelGeneratorService
from app.services.historical.historical_backtesting_policy import HistoricalBacktestingPolicyService
from app.services.historical.historical_feature_store import HistoricalFeatureStoreService
from app.services.historical.historical_training_dataset import HistoricalTrainingDatasetService
from app.services.historical.historical_model_persistence import HistoricalModelPersistenceService
from app.services.historical.historical_model_persistence_schemas import (
    HistoricalModelPersistenceConfig,
    HistoricalModelPersistenceSummary,
    ModelBundleVerificationSummary,
    PersistedModelReference,
)
from app.services.historical.historical_retraining_schedule_schemas import (
    HistoricalRetrainingContext,
    HistoricalRetrainingScheduleConfig,
    HistoricalRetrainingScheduleSummary,
    RetrainingPipelineStep,
)
from app.services.historical.historical_ml_scoring_schemas import (
    HistoricalMLScoringConfig,
    HistoricalMLScoringSummary,
    MLScoreExplanationRecord,
    MLScoredCandidateRecord,
    MLScoringCandidateInput,
)
from app.services.historical.historical_feature_importance_review_schemas import (
    FeatureDriftRecord,
    FeatureImportanceFoldReview,
    FeatureImportanceRecord,
    HistoricalFeatureImportanceReviewConfig,
    HistoricalFeatureImportanceReviewSummary,
)
from app.services.historical.historical_walkforward_validation_schemas import (
    HistoricalWalkForwardValidationConfig,
    HistoricalWalkForwardValidationSummary,
    WalkForwardAggregateMetrics,
    WalkForwardFoldPlan,
    WalkForwardFoldResult,
)
from app.services.historical.historical_baseline_model_schemas import (
    BaselineModelArtifactRecord,
    BaselineModelHyperparameters,
    BaselineModelTrainingSummary,
)
from app.services.historical.historical_universe_snapshot import HistoricalUniverseSnapshotService
from app.services.historical.feature_schemas import FeatureBuildSummary, HistoricalFeatureRecord
from app.services.historical.historical_replay_schemas import (
    HistoricalReplayPolicy,
    HistoricalReplayRecord,
    HistoricalReplaySummary,
)
from app.services.historical.historical_backtesting_policy_schemas import (
    BacktestingPolicyVersionRecord,
    HistoricalBacktestingPolicy,
    ResolvedBacktestingPolicyRecord,
)
from app.services.historical.historical_label_schemas import (
    HistoricalLabelGenerationSummary,
    HistoricalLabelPolicy,
    HistoricalReplayLabelRecord,
    LabelPolicyVersionRecord,
)
from app.services.historical.feature_store_schemas import (
    FeatureDefinitionVersionRecord,
    HistoricalFeatureStoreBuildSummary,
    HistoricalFeatureStoreRowRecord,
)
from app.services.historical.historical_training_dataset_schemas import (
    HistoricalTrainingDataset,
    TrainingDatasetBuildSummary,
    TrainingDatasetRowRecord,
    TrainingDatasetVersionRecord,
)
from app.services.historical.regime_detection import RegimeDetectionService
from app.services.historical.snapshot_persistence import AISnapshotPersistenceService
from app.services.historical.universe_composer import UniverseComposerService
from app.services.historical.sentiment_scoring import SentimentScoringService
from app.services.historical.snapshot_persistence_schemas import SnapshotPersistenceSummary
from app.services.historical.regime_detection_schemas import (
    RegimeDetectionRecord,
    RegimeDetectionSummary,
)
from app.services.historical.sentiment_scoring_schemas import (
    SentimentInputRecord,
    SentimentScoreRecord,
    SentimentScoreSummary,
)
from app.services.historical.technical_scoring import (
    TechnicalScoreRecord,
    TechnicalScoreSummary,
    TechnicalScoringService,
)
from app.services.historical.universe_composer_schemas import (
    UniverseCandidateRecord,
    UniverseCompositionSummary,
)
from app.services.historical.rate_limiter import RateLimiter
from app.services.historical.retention import CandleRetentionPolicy, retention_bucket_for_timeframe
from app.services.historical.schemas import (
    BackfillPlan,
    HistoricalBackfillRequest,
    HistoricalCandleRecord,
    IngestionSummary,
)


def __getattr__(name: str):
    if name == "HistoricalBaselineModelService":
        from app.services.historical.historical_baseline_model import HistoricalBaselineModelService

        return HistoricalBaselineModelService

    if name == "HistoricalWalkForwardValidationService":
        from app.services.historical.historical_walkforward_validation import (
            HistoricalWalkForwardValidationService,
        )

        return HistoricalWalkForwardValidationService

    if name == "HistoricalFeatureImportanceReviewService":
        from app.services.historical.historical_feature_importance_review import (
            HistoricalFeatureImportanceReviewService,
        )

        return HistoricalFeatureImportanceReviewService

    if name == "HistoricalMLScoringService":
        from app.services.historical.historical_ml_scoring import HistoricalMLScoringService

        return HistoricalMLScoringService

    if name == "HistoricalRetrainingScheduleService":
        from app.services.historical.historical_retraining_schedule import (
            HistoricalRetrainingScheduleService,
        )

        return HistoricalRetrainingScheduleService

    if name == "HistoricalMLTransparencyService":
        from app.services.historical.historical_ml_transparency import HistoricalMLTransparencyService

        return HistoricalMLTransparencyService

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AIResearchSchedulerService",
    "AISnapshotPersistenceService",
    "BackfillPlan",
    "BackfillPlanner",
    "BacktestingPolicyVersionRecord",
    "BaselineModelArtifactRecord",
    "BaselineModelHyperparameters",
    "BaselineModelTrainingSummary",
    "CandleRetentionPolicy",
    "FeatureBuildSummary",
    "FeatureDefinitionVersionRecord",
    "FeatureDriftRecord",
    "FeatureImportanceFoldReview",
    "FeatureImportanceRecord",
    "HistoricalBackfillRequest",
    "HistoricalBacktestingPolicy",
    "HistoricalBacktestingPolicyService",
    "HistoricalBaselineModelService",
    "HistoricalCandleRecord",
    "HistoricalFeatureImportanceReviewConfig",
    "HistoricalFeatureImportanceReviewService",
    "HistoricalFeatureImportanceReviewSummary",
    "HistoricalFeatureRecord",
    "HistoricalFeatureStoreBuildSummary",
    "HistoricalFeatureStoreRowRecord",
    "HistoricalFeatureStoreService",
    "HistoricalLabelGenerationSummary",
    "HistoricalLabelGeneratorService",
    "HistoricalLabelPolicy",
    "HistoricalMLScoringConfig",
    "HistoricalMLScoringService",
    "HistoricalMLScoringSummary",
    "HistoricalMLTransparencyService",
    "HistoricalModelPersistenceConfig",
    "HistoricalModelPersistenceService",
    "HistoricalModelPersistenceSummary",
    "HistoricalReplayLabelRecord",
    "HistoricalReplayPolicy",
    "HistoricalReplayRecord",
    "HistoricalReplaySummary",
    "HistoricalRetrainingContext",
    "HistoricalRetrainingScheduleConfig",
    "HistoricalRetrainingScheduleService",
    "HistoricalRetrainingScheduleSummary",
    "HistoricalStrategyReplayService",
    "HistoricalTrainingDataset",
    "HistoricalTrainingDatasetService",
    "HistoricalUniverseSnapshotService",
    "HistoricalWalkForwardValidationConfig",
    "HistoricalWalkForwardValidationService",
    "HistoricalWalkForwardValidationSummary",
    "IngestionSummary",
    "LabelPolicyVersionRecord",
    "MLScoreExplanationRecord",
    "MLScoredCandidateRecord",
    "MLScoringCandidateInput",
    "ModelBundleVerificationSummary",
    "PersistedModelReference",
    "RateLimiter",
    "RegimeDetectionRecord",
    "RegimeDetectionService",
    "RegimeDetectionSummary",
    "ResolvedBacktestingPolicyRecord",
    "RetrainingPipelineStep",
    "SentimentInputRecord",
    "SentimentScoreRecord",
    "SentimentScoreSummary",
    "SentimentScoringService",
    "SnapshotPersistenceSummary",
    "TechnicalScoreRecord",
    "TechnicalScoreSummary",
    "TechnicalScoringService",
    "TrainingDatasetBuildSummary",
    "TrainingDatasetRowRecord",
    "TrainingDatasetVersionRecord",
    "UniverseCandidateRecord",
    "UniverseComposerService",
    "UniverseCompositionSummary",
    "WalkForwardAggregateMetrics",
    "WalkForwardFoldPlan",
    "WalkForwardFoldResult",
    "retention_bucket_for_timeframe",
]