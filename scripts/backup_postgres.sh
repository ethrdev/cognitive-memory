#!/bin/bash
#
# PostgreSQL Backup Script for Cognitive Memory System
# Story 3.6: PostgreSQL Backup Strategy Implementation
#
# Features:
# - Daily pg_dump backups with Custom Format (-Fc)
# - 7-day backup retention
# - Comprehensive logging with timestamps and metrics
# - Consecutive failure tracking
# - Proper error handling and cleanup
#
# Usage: bash scripts/backup_postgres.sh
# Cron:  0 3 * * * /path/to/scripts/backup_postgres.sh >> /var/log/cognitive-memory/backup.log 2>&1

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

# Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly BACKUP_DIR="/backups/postgres"
readonly LOG_DIR="/var/log/cognitive-memory"
readonly LOG_FILE="${LOG_DIR}/backup.log"
readonly RETENTION_DAYS=7
readonly MIN_BACKUP_SIZE_MB=1
readonly FAILURE_COUNTER_FILE="${LOG_DIR}/.backup_failures"
readonly LOCK_FILE="/tmp/backup_postgres.lock"

# Cleanup function for trap
cleanup() {
    local exit_code=$?
    # Remove lock file
    rm -f "${LOCK_FILE}"

    if [ $exit_code -ne 0 ]; then
        log "ERROR" "Backup script exited with error code ${exit_code}"
    fi
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Logging function
log() {
    local level="$1"
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}"
}

# Check for concurrent execution
acquire_lock() {
    if [ -e "${LOCK_FILE}" ]; then
        local lock_pid=$(cat "${LOCK_FILE}" 2>/dev/null || echo "unknown")
        log "ERROR" "Another backup is already running (PID: ${lock_pid}). Exiting."
        exit 1
    fi

    # Create lock file with current PID
    echo $$ > "${LOCK_FILE}"
    log "INFO" "Acquired backup lock (PID: $$)"
}

# Load environment variables from .env file
load_env() {
    local env_file="${PROJECT_ROOT}/.env"

    if [ ! -f "${env_file}" ]; then
        # Try .env.development as fallback
        env_file="${PROJECT_ROOT}/.env.development"
    fi

    if [ ! -f "${env_file}" ]; then
        log "ERROR" "No .env or .env.development file found at ${PROJECT_ROOT}"
        exit 1
    fi

    log "INFO" "Loading environment variables from ${env_file}"

    # Load environment variables (export for pg_dump to use)
    set -a
    source "${env_file}"
    set +a

    # Verify DATABASE_URL is set
    if [ -z "${DATABASE_URL}" ]; then
        log "ERROR" "DATABASE_URL not found in environment file"
        exit 1
    fi

    # Extract database components from DATABASE_URL
    # Format: postgresql://user:password@host:port/dbname
    if [[ ${DATABASE_URL} =~ postgresql://([^:]+):([^@]+)@([^:]+):([^/]+)/(.+) ]]; then
        export PGUSER="${BASH_REMATCH[1]}"
        export PGPASSWORD="${BASH_REMATCH[2]}"
        export PGHOST="${BASH_REMATCH[3]}"
        export PGPORT="${BASH_REMATCH[4]}"
        export PGDATABASE="${BASH_REMATCH[5]}"

        log "INFO" "Extracted database credentials (user: ${PGUSER}, database: ${PGDATABASE})"
    else
        log "ERROR" "Invalid DATABASE_URL format"
        exit 1
    fi
}

# Create necessary directories
create_directories() {
    # Create backup directory with restricted permissions
    if [ ! -d "${BACKUP_DIR}" ]; then
        log "INFO" "Creating backup directory: ${BACKUP_DIR}"
        mkdir -p "${BACKUP_DIR}"
        chmod 700 "${BACKUP_DIR}"
        log "INFO" "Backup directory created with chmod 700"
    fi

    # Create log directory if needed
    if [ ! -d "${LOG_DIR}" ]; then
        log "INFO" "Creating log directory: ${LOG_DIR}"
        mkdir -p "${LOG_DIR}"
        chmod 750 "${LOG_DIR}"
        log "INFO" "Log directory created with chmod 750"
    fi
}

# Execute pg_dump backup
execute_backup() {
    local backup_date=$(date '+%Y-%m-%d')
    local backup_file="${BACKUP_DIR}/cognitive_memory_${backup_date}.dump"
    local start_time=$(date +%s)

    log "INFO" "Starting PostgreSQL backup..."
    log "INFO" "Backup file: ${backup_file}"
    log "INFO" "Database: ${PGDATABASE} on ${PGHOST}:${PGPORT}"

    # Execute pg_dump with Custom Format (-Fc)
    # -Fc: Custom format (compressed, supports parallel restore)
    # -v: Verbose mode for detailed logging
    if pg_dump -Fc -v -d "${PGDATABASE}" -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -f "${backup_file}"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))

        # Get backup file size
        local file_size_bytes=$(stat -f%z "${backup_file}" 2>/dev/null || stat -c%s "${backup_file}" 2>/dev/null)
        local file_size_mb=$((file_size_bytes / 1024 / 1024))

        log "INFO" "Backup completed successfully"
        log "INFO" "Duration: ${duration} seconds"
        log "INFO" "Backup size: ${file_size_mb} MB (${file_size_bytes} bytes)"

        # Validate backup file size
        if [ ${file_size_mb} -lt ${MIN_BACKUP_SIZE_MB} ]; then
            log "ERROR" "Backup file too small (${file_size_mb} MB < ${MIN_BACKUP_SIZE_MB} MB threshold)"
            log "ERROR" "Backup may be incomplete or corrupted"
            increment_failure_counter
            return 1
        fi

        # Set backup file permissions to owner-only read/write
        chmod 600 "${backup_file}"
        log "INFO" "Backup file permissions set to chmod 600"

        # Reset failure counter on success
        reset_failure_counter

        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))

        log "ERROR" "pg_dump failed after ${duration} seconds"
        log "ERROR" "Check PostgreSQL connection and credentials"
        increment_failure_counter
        return 1
    fi
}

# Rotate old backups (keep last 7 days)
rotate_backups() {
    log "INFO" "Starting backup rotation (retention: ${RETENTION_DAYS} days)"

    local deleted_count=0
    local retention_seconds=$((RETENTION_DAYS * 24 * 60 * 60))
    local current_time=$(date +%s)

    # Find and delete backups older than retention period
    for backup_file in "${BACKUP_DIR}"/cognitive_memory_*.dump; do
        if [ -f "${backup_file}" ]; then
            local file_time=$(stat -f%m "${backup_file}" 2>/dev/null || stat -c%Y "${backup_file}" 2>/dev/null)
            local file_age=$((current_time - file_time))

            if [ ${file_age} -gt ${retention_seconds} ]; then
                log "INFO" "Deleting old backup: $(basename ${backup_file}) (age: $((file_age / 86400)) days)"
                rm -f "${backup_file}"
                ((deleted_count++))
            fi
        fi
    done

    log "INFO" "Backup rotation complete (deleted ${deleted_count} old backups)"
}

# Track consecutive failures
increment_failure_counter() {
    local failure_count=0

    if [ -f "${FAILURE_COUNTER_FILE}" ]; then
        failure_count=$(cat "${FAILURE_COUNTER_FILE}")
    fi

    ((failure_count++))
    echo ${failure_count} > "${FAILURE_COUNTER_FILE}"

    log "INFO" "Consecutive failure count: ${failure_count}"

    # Escalate to ERROR level after 2 consecutive failures
    if [ ${failure_count} -ge 2 ]; then
        log "ERROR" "ALERT: ${failure_count} consecutive backup failures detected"
        log "ERROR" "Immediate attention required - backup system may be failing"
    fi
}

# Reset failure counter on successful backup
reset_failure_counter() {
    if [ -f "${FAILURE_COUNTER_FILE}" ]; then
        local previous_failures=$(cat "${FAILURE_COUNTER_FILE}")
        if [ ${previous_failures} -gt 0 ]; then
            log "INFO" "Backup recovered after ${previous_failures} consecutive failures"
        fi
    fi

    echo 0 > "${FAILURE_COUNTER_FILE}"
}

# Main execution
main() {
    log "INFO" "=========================================="
    log "INFO" "PostgreSQL Backup Script Started"
    log "INFO" "=========================================="

    # Acquire lock to prevent concurrent execution
    acquire_lock

    # Load environment variables and credentials
    load_env

    # Create necessary directories
    create_directories

    # Execute backup
    if execute_backup; then
        log "INFO" "Backup execution successful"
    else
        log "ERROR" "Backup execution failed"
        exit 1
    fi

    # Rotate old backups
    rotate_backups

    log "INFO" "=========================================="
    log "INFO" "PostgreSQL Backup Script Completed"
    log "INFO" "=========================================="
}

# Run main function
main
