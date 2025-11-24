"""
Budget Alerting Module

Sends email and Slack notifications when budget thresholds are exceeded.
Implements alert tracking to prevent duplicate notifications.
"""

from __future__ import annotations

import json
import logging
import smtplib
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

import requests

from mcp_server.budget.budget_monitor import check_budget_threshold
from mcp_server.config import get_config
from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


def _send_email_alert(
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> bool:
    """
    Send email alert using SMTP.

    Reads SMTP configuration from environment variables:
    - SMTP_HOST: SMTP server hostname
    - SMTP_PORT: SMTP server port (default 587)
    - SMTP_USER: SMTP username
    - SMTP_PASSWORD: SMTP password
    - SMTP_FROM: From email address

    Args:
        to_email: Recipient email address
        subject: Email subject
        body_text: Plain text email body
        body_html: Optional HTML email body

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    import os

    # Get SMTP configuration from environment
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    # Validate configuration
    if not smtp_host or not smtp_user or not smtp_password:
        logger.warning(
            "SMTP configuration incomplete. "
            "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD environment variables."
        )
        return False

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to_email

        # Attach plain text and HTML parts
        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info(f"Budget alert email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(
            f"Failed to send email alert: {type(e).__name__}: {e}"
        )
        return False


def _send_slack_alert(webhook_url: str, message: str, details: Dict[str, Any]) -> bool:
    """
    Send Slack notification via webhook.

    Args:
        webhook_url: Slack webhook URL
        message: Alert message
        details: Budget status details

    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    try:
        # Build Slack message payload
        payload = {
            "text": f"⚠️ Budget Alert: {message}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "⚠️ Budget Alert",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Projected Cost:*\n€{details['projected_cost']:.2f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Budget Limit:*\n€{details['budget_limit']:.2f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Utilization:*\n{details['utilization_pct']:.1f}%"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Current Cost:*\n€{details['current_cost']:.2f}"
                        }
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Days elapsed: {details['days_elapsed']} / {details['days_in_month']}"
                        }
                    ]
                }
            ]
        }

        # Send to Slack
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            logger.info("Budget alert sent to Slack")
            return True
        else:
            logger.error(
                f"Slack webhook returned status {response.status_code}: "
                f"{response.text}"
            )
            return False

    except Exception as e:
        logger.error(
            f"Failed to send Slack alert: {type(e).__name__}: {e}"
        )
        return False


def _log_alert(
    alert_type: str,
    projected_cost: float,
    budget_limit: float,
    utilization_pct: float,
    alert_sent: bool,
    notification_methods: str,
) -> None:
    """
    Log budget alert to database for tracking and preventing duplicates.

    Creates budget_alerts table if it doesn't exist.

    Args:
        alert_type: Type of alert ('threshold' or 'exceeded')
        projected_cost: Projected monthly cost
        budget_limit: Monthly budget limit
        utilization_pct: Budget utilization percentage
        alert_sent: Whether notification was successfully sent
        notification_methods: Notification methods used (e.g., 'email,slack')
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS budget_alerts (
                    id SERIAL PRIMARY KEY,
                    alert_date DATE NOT NULL,
                    alert_type VARCHAR(50) NOT NULL,
                    projected_cost FLOAT NOT NULL,
                    budget_limit FLOAT NOT NULL,
                    utilization_pct FLOAT NOT NULL,
                    alert_sent BOOLEAN NOT NULL,
                    notification_methods VARCHAR(255),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            # Create index for duplicate prevention (one alert per type per day)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_budget_alerts_unique
                ON budget_alerts(alert_date, alert_type);
            """)

            # Insert alert record
            today = date.today()
            cursor.execute(
                """
                INSERT INTO budget_alerts (
                    alert_date, alert_type, projected_cost, budget_limit,
                    utilization_pct, alert_sent, notification_methods
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    today,
                    alert_type,
                    projected_cost,
                    budget_limit,
                    utilization_pct,
                    alert_sent,
                    notification_methods,
                ),
            )

            conn.commit()

            logger.info(
                f"Budget alert logged: type={alert_type}, "
                f"cost=€{projected_cost:.2f}, sent={alert_sent}"
            )

    except Exception as e:
        logger.error(
            f"Failed to log budget alert: {type(e).__name__}: {e}"
        )


def _check_alert_sent_today(alert_type: str) -> bool:
    """
    Check if alert of this type was already sent today.

    Args:
        alert_type: Type of alert ('threshold' or 'exceeded')

    Returns:
        bool: True if alert already sent today, False otherwise
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check if table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'budget_alerts'
                );
            """)
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                return False

            # Check for existing alert today
            today = date.today()
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM budget_alerts
                WHERE alert_date = %s AND alert_type = %s
                """,
                (today, alert_type),
            )

            count = cursor.fetchone()[0]
            return count > 0

    except Exception as e:
        logger.error(
            f"Failed to check alert history: {type(e).__name__}: {e}"
        )
        return False


def check_and_send_alerts() -> Dict[str, Any]:
    """
    Check budget status and send alerts if thresholds are exceeded.

    Reads alert configuration from config.yaml:
    - budget.alert_email: Email address for alerts (optional)
    - budget.alert_slack_webhook: Slack webhook URL (optional)

    Alert Types:
    - Threshold Alert: Sent when projected cost exceeds alert_threshold_pct (80% default)
    - Exceeded Alert: Sent when projected cost exceeds monthly_limit_eur

    Duplicate Prevention:
    - Only one alert of each type per day
    - Tracks sent alerts in budget_alerts table

    Returns:
        Dict with:
        - budget_status: Dict from check_budget_threshold()
        - alert_sent: bool (True if any alert sent)
        - alert_type: str ('threshold', 'exceeded', or None)
        - notification_methods: List[str] (methods used: 'email', 'slack')

    Example:
        >>> result = check_and_send_alerts()
        >>> if result['alert_sent']:
        ...     print(f"Alert sent: {result['alert_type']}")
        >>> else:
        ...     print("No alerts needed")
    """
    # Check budget status
    status = check_budget_threshold()

    # Determine if alert should be sent
    alert_type = None
    if status['budget_exceeded']:
        alert_type = 'exceeded'
    elif status['alert_triggered']:
        alert_type = 'threshold'

    # No alert needed
    if alert_type is None:
        logger.debug("Budget status OK, no alerts needed")
        return {
            "budget_status": status,
            "alert_sent": False,
            "alert_type": None,
            "notification_methods": [],
        }

    # Check if alert already sent today
    if _check_alert_sent_today(alert_type):
        logger.info(f"Alert of type '{alert_type}' already sent today, skipping")
        return {
            "budget_status": status,
            "alert_sent": False,
            "alert_type": alert_type,
            "notification_methods": [],
            "reason": "duplicate_prevention",
        }

    # Load alert configuration
    try:
        config = get_config()
        budget_config = config.get('budget', {})
        alert_email = budget_config.get('alert_email', '')
        alert_slack_webhook = budget_config.get('alert_slack_webhook', '')
    except Exception as e:
        logger.warning(f"Failed to load alert config: {e}")
        alert_email = ''
        alert_slack_webhook = ''

    # Build alert message
    if alert_type == 'exceeded':
        message = (
            f"Budget exceeded! Projected monthly cost €{status['projected_cost']:.2f} "
            f"exceeds limit of €{status['budget_limit']:.2f} "
            f"({status['utilization_pct']:.1f}% utilization)"
        )
    else:  # threshold
        message = (
            f"Budget threshold reached! Projected monthly cost €{status['projected_cost']:.2f} "
            f"is at {status['utilization_pct']:.1f}% of €{status['budget_limit']:.2f} limit"
        )

    # Send notifications
    notification_methods = []
    alert_sent = False

    # Email notification
    if alert_email:
        email_body = f"""
Budget Alert - Cognitive Memory System

{message}

Budget Details:
- Current Cost (MTD): €{status['current_cost']:.2f}
- Projected Monthly Cost: €{status['projected_cost']:.2f}
- Monthly Budget Limit: €{status['budget_limit']:.2f}
- Budget Utilization: {status['utilization_pct']:.1f}%

Month Progress:
- Days Elapsed: {status['days_elapsed']} / {status['days_in_month']}
- Days Remaining: {status['days_remaining']}
- Average Daily Cost: €{status['avg_daily_cost']:.4f}

Action Required:
{'- URGENT: Reduce API usage immediately' if alert_type == 'exceeded' else '- Monitor usage closely to stay within budget'}

For detailed cost breakdown, run:
    python -m mcp_server.budget.cli dashboard
"""
        if _send_email_alert(
            to_email=alert_email,
            subject=f"⚠️ Budget Alert: {alert_type.title()}",
            body_text=email_body,
        ):
            notification_methods.append('email')
            alert_sent = True

    # Slack notification
    if alert_slack_webhook:
        if _send_slack_alert(alert_slack_webhook, message, status):
            notification_methods.append('slack')
            alert_sent = True

    # Log alert
    _log_alert(
        alert_type=alert_type,
        projected_cost=status['projected_cost'],
        budget_limit=status['budget_limit'],
        utilization_pct=status['utilization_pct'],
        alert_sent=alert_sent,
        notification_methods=','.join(notification_methods) if notification_methods else None,
    )

    logger.info(
        f"Budget alert processed: type={alert_type}, sent={alert_sent}, "
        f"methods={notification_methods}"
    )

    return {
        "budget_status": status,
        "alert_sent": alert_sent,
        "alert_type": alert_type,
        "notification_methods": notification_methods,
    }
