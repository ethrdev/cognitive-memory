"""
Validation Package for Story 1.12

This package provides Inter-Rater Reliability (IRR) validation capabilities
for ground truth queries with dual judge scores.

Modules:
- irr_validator: Core IRR validation with Cohen's Kappa calculations
- contingency: Contingency plan components (human tiebreaker, bias analysis, recalibration)
"""

from .contingency import (
    ContingencyAction,
    ContingencyManager,
    HighDisagreementAnalyzer,
    JudgeRecalibration,
    ThresholdAdjustmentRecommender,
)
from .irr_validator import IRRValidator, ValidationResults, run_irr_validation

__all__ = [
    "IRRValidator",
    "ValidationResults",
    "run_irr_validation",
    "ContingencyManager",
    "HighDisagreementAnalyzer",
    "ThresholdAdjustmentRecommender",
    "JudgeRecalibration",
    "ContingencyAction",
]

__version__ = "1.0.0"
__author__ = "Story 1.12 Development"
