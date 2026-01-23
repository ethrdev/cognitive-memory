"""
[P0] Budget Monitoring Tests

Tests for budget monitoring functionality including cost tracking,
alerts, and budget enforcement.

Priority: P0 (Critical) - Budget monitoring is critical for cost control
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import asyncio

from mcp_server.budget.budget_monitor import BudgetMonitor
from mcp_server.budget.budget_alerts import BudgetAlertManager
from mcp_server.db.cost_logger import CostLogger


@pytest.mark.P0
class TestBudgetMonitor:
    """P0 tests for budget monitoring critical functionality."""

    @pytest.fixture
    def budget_monitor(self):
        """Create budget monitor instance for testing."""
        return BudgetMonitor(
            monthly_budget=1000.0,
            warning_threshold=0.8,
            critical_threshold=0.95,
        )

    @pytest.fixture
    def mock_cost_logger(self):
        """Mock cost logger."""
        return Mock(spec=CostLogger)

    @pytest.mark.asyncio
    async def test_budget_monitor_initialization(self):
        """[P0] Budget monitor should initialize with correct settings."""
        monitor = BudgetMonitor(
            monthly_budget=2000.0,
            warning_threshold=0.75,
            critical_threshold=0.90,
        )

        assert monitor.monthly_budget == 2000.0
        assert monitor.warning_threshold == 0.75
        assert monitor.critical_threshold == 0.90
        assert monitor.current_spending == 0.0
        assert monitor.alert_manager is not None

    @pytest.mark.asyncio
    async def test_track_cost_updates_spending(self, budget_monitor, mock_cost_logger):
        """[P0] Tracking cost should update current spending."""
        # GIVEN: Budget monitor initialized
        budget_monitor.cost_logger = mock_cost_logger

        # WHEN: Cost is tracked
        await budget_monitor.track_cost(
            operation="test_operation",
            cost=50.0,
            metadata={"test": True}
        )

        # THEN: Current spending should increase
        assert budget_monitor.current_spending == 50.0
        mock_cost_logger.log_cost.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_budget_triggers_warning(self, budget_monitor, mock_cost_logger):
        """[P0] Check budget should trigger warning at threshold."""
        # GIVEN: Budget monitor at 80% of budget
        budget_monitor.current_spending = 800.0  # 80% of 1000
        budget_monitor.cost_logger = mock_cost_logger
        budget_monitor.alert_manager = Mock(spec=BudgetAlertManager)

        # WHEN: Budget is checked
        result = await budget_monitor.check_budget()

        # THEN: Warning alert should be triggered
        assert result["status"] == "warning"
        assert result["percentage"] == 80.0
        assert result["remaining"] == 200.0
        budget_monitor.alert_manager.send_warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_budget_triggers_critical(self, budget_monitor, mock_cost_logger):
        """[P0] Check budget should trigger critical at 95% threshold."""
        # GIVEN: Budget monitor at 95% of budget
        budget_monitor.current_spending = 950.0  # 95% of 1000
        budget_monitor.cost_logger = mock_cost_logger
        budget_monitor.alert_manager = Mock(spec=BudgetAlertManager)

        # WHEN: Budget is checked
        result = await budget_monitor.check_budget()

        # THEN: Critical alert should be triggered
        assert result["status"] == "critical"
        assert result["percentage"] == 95.0
        budget_monitor.alert_manager.send_critical.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_budget_allows_normal_operation(self, budget_monitor, mock_cost_logger):
        """[P0] Check budget should allow normal operation under threshold."""
        # GIVEN: Budget monitor at 60% of budget
        budget_monitor.current_spending = 600.0  # 60% of 1000
        budget_monitor.cost_logger = mock_cost_logger
        budget_monitor.alert_manager = Mock(spec=BudgetAlertManager)

        # WHEN: Budget is checked
        result = await budget_monitor.check_budget()

        # THEN: Normal operation should continue
        assert result["status"] == "normal"
        assert result["percentage"] == 60.0
        budget_monitor.alert_manager.send_warning.assert_not_called()
        budget_monitor.alert_manager.send_critical.assert_not_called()

    @pytest.mark.asyncio
    async def test_reset_monthly_budget(self, budget_monitor, mock_cost_logger):
        """[P1] Reset monthly budget should clear spending."""
        # GIVEN: Budget monitor with existing spending
        budget_monitor.current_spending = 500.0
        budget_monitor.cost_logger = mock_cost_logger

        # WHEN: Monthly budget is reset
        await budget_monitor.reset_monthly_budget()

        # THEN: Spending should be reset
        assert budget_monitor.current_spending == 0.0
        mock_cost_logger.reset_monthly.assert_called_once()


@pytest.mark.P1
class TestBudgetAlertManager:
    """P1 tests for budget alert management."""

    @pytest.fixture
    def alert_manager(self):
        """Create alert manager instance."""
        return BudgetAlertManager()

    @pytest.mark.asyncio
    async def test_send_warning_alert(self, alert_manager):
        """[P1] Send warning alert should log appropriate message."""
        with patch('mcp_server.budget.budget_alerts.logger.warning') as mock_log:
            # WHEN: Warning alert is sent
            await alert_manager.send_warning(
                budget_percentage=80.0,
                remaining_budget=200.0,
                monthly_budget=1000.0
            )

            # THEN: Warning should be logged
            mock_log.assert_called_once()
            assert "80%" in mock_log.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_critical_alert(self, alert_manager):
        """[P1] Send critical alert should log error and may block operations."""
        with patch('mcp_server.budget.budget_alerts.logger.error') as mock_log:
            # WHEN: Critical alert is sent
            await alert_manager.send_critical(
                budget_percentage=95.0,
                remaining_budget=50.0,
                monthly_budget=1000.0
            )

            # THEN: Error should be logged
            mock_log.assert_called_once()
            assert "95%" in mock_log.call_args[0][0]


@pytest.mark.P2
class TestBudgetIntegration:
    """P2 integration tests for budget system."""

    @pytest.mark.asyncio
    async def test_full_budget_cycle(self):
        """[P2] Full budget cycle from initialization to critical threshold."""
        # GIVEN: Budget monitor with 1000 budget
        monitor = BudgetMonitor(monthly_budget=1000.0)

        # WHEN: Multiple costs are tracked
        await monitor.track_cost("operation_1", 300.0)
        await monitor.track_cost("operation_2", 200.0)
        await monitor.track_cost("operation_3", 500.0)

        # THEN: Total should be accumulated correctly
        assert monitor.current_spending == 1000.0

    @pytest.mark.asyncio
    async def test_budget_enforcement_at_critical(self):
        """[P2] Budget enforcement should prevent operations at critical threshold."""
        # GIVEN: Budget monitor at critical threshold
        monitor = BudgetMonitor(monthly_budget=1000.0, critical_threshold=0.95)
        monitor.current_spending = 960.0  # 96%

        # WHEN: Checking if operation is allowed
        allowed = await monitor.is_operation_allowed(cost=100.0)

        # THEN: Operation should be blocked
        assert allowed is False

    @pytest.mark.asyncio
    async def test_budget_enforcement_allows_safe_operation(self):
        """[P2] Budget enforcement should allow operations under threshold."""
        # GIVEN: Budget monitor under threshold
        monitor = BudgetMonitor(monthly_budget=1000.0, critical_threshold=0.95)
        monitor.current_spending = 500.0  # 50%

        # WHEN: Checking if operation is allowed
        allowed = await monitor.is_operation_allowed(cost=100.0)

        # THEN: Operation should be allowed
        assert allowed is True
