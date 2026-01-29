#!/usr/bin/env python3
"""Aegis Bridge - Supabase to Archon72 petition integration.

Direct mode: Process pending petitions from Supabase and submit to Archon72.

Usage:
    python main.py                    # Process one batch
    python main.py --dry-run          # Dry run (don't submit to Archon72)
    python main.py --continuous       # Keep running and poll for new petitions
    python main.py --interval 30      # Poll every 30 seconds (with --continuous)

Environment Variables:
    SUPABASE_URL          - Supabase project URL (required)
    SUPABASE_SERVICE_KEY  - Supabase service role key (required)
    ARCHON72_API_URL      - Archon72 API base URL (required)
    BATCH_SIZE            - Petitions per batch (default: 100)
    MAX_RETRIES           - Max retry attempts (default: 3)
    DRY_RUN               - Set to "true" for dry run mode
"""

import argparse
import asyncio
import logging
import os
import sys

from src.clients.archon72 import Archon72Client
from src.clients.supabase import SupabaseClient
from src.config import load_config
from src.extractor import PetitionExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("aegis-bridge")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Aegis Bridge - Supabase to Archon72 petition integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't actually submit to Archon72",
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Continuous mode - keep polling for new petitions",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Poll interval in seconds for continuous mode (default: 60)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override batch size (default: from env or 100)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output (debug logging)",
    )

    return parser.parse_args()


async def run_once(extractor: PetitionExtractor) -> int:
    """Run one batch of petition processing.

    Args:
        extractor: Configured petition extractor.

    Returns:
        Number of petitions processed.
    """
    result = await extractor.process_batch()

    if result.total == 0:
        logger.info("No petitions to process")
        return 0

    logger.info(
        f"Processed {result.total} petitions: "
        f"{result.successful} successful, {result.failed} failed"
    )

    # Log individual failures
    for r in result.results:
        if not r.success:
            retry_status = "will retry" if r.should_retry else "permanent failure"
            logger.warning(f"  {r.petition_id}: {r.error} ({retry_status})")

    return result.total


async def run_continuous(extractor: PetitionExtractor, interval: int) -> None:
    """Run continuously, polling for new petitions.

    Args:
        extractor: Configured petition extractor.
        interval: Seconds between polls.
    """
    logger.info(f"Starting continuous mode (polling every {interval}s)")
    logger.info("Press Ctrl+C to stop")

    while True:
        try:
            await run_once(extractor)
        except Exception as e:
            logger.exception(f"Error during processing: {e}")

        logger.debug(f"Sleeping for {interval} seconds...")
        await asyncio.sleep(interval)


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1

    # Override from CLI args
    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
        config = load_config()  # Reload with dry run

    if args.batch_size:
        os.environ["BATCH_SIZE"] = str(args.batch_size)
        config = load_config()

    # Log configuration
    logger.info("Aegis Bridge starting")
    logger.info(f"  Supabase URL: {config.supabase.url}")
    logger.info(f"  Archon72 URL: {config.archon72.api_url}")
    logger.info(f"  Batch size: {config.processing.batch_size}")
    logger.info(f"  Max retries: {config.processing.max_retries}")
    logger.info(f"  Dry run: {config.processing.dry_run}")

    # Initialize clients
    supabase = SupabaseClient(config.supabase)
    archon72 = Archon72Client(config.archon72)

    # Check Archon72 health (unless dry run)
    if not config.processing.dry_run:
        logger.info("Checking Archon72 API health...")
        if await archon72.health_check():
            logger.info("  Archon72 API is healthy")
        else:
            logger.warning("  Archon72 API health check failed (continuing anyway)")

    # Create extractor
    extractor = PetitionExtractor(supabase, archon72, config.processing)

    # Run
    try:
        if args.continuous:
            await run_continuous(extractor, args.interval)
        else:
            count = await run_once(extractor)
            logger.info(f"Done. Processed {count} petitions.")
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
