"""
Crexi Automation - Playwright-based automated CSV export from Crexi.

Automates the process of:
1. Logging into Crexi
2. Searching for a location
3. Applying filters
4. Downloading CSV export
5. Parsing and importing results

Security: Logs every session, never modifies account or contacts brokers.
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

from playwright.async_api import async_playwright, Browser, Page, Download
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.crexi_parser import parse_crexi_csv, filter_opportunities, import_to_database, ImportResult

logger = logging.getLogger(__name__)

# Security: Log all Crexi automation sessions
CREXI_SESSION_LOG = Path("logs/crexi_sessions.log")


class CrexiAutomationError(Exception):
    """Raised when Crexi automation fails."""
    pass


class CrexiAutomation:
    """Automates Crexi CSV exports using Playwright."""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None  # Store playwright instance for cleanup
        self._temp_dir: Optional[str] = None
        self._download_path: Optional[str] = None
        
    async def __aenter__(self):
        """Context manager entry."""
        await self.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.cleanup()
    
    async def setup(self):
        """Initialize browser and page."""
        self._temp_dir = tempfile.mkdtemp(prefix="crexi_export_")
        logger.info(f"Created temp directory: {self._temp_dir}")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            downloads_path=self._temp_dir
        )
        
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            accept_downloads=True
        )
        
        self.page = await context.new_page()
        
        # Log session start
        self._log_session("Session started")
    
    async def cleanup(self):
        """Clean up browser and temp files."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        # Clean up temp directory
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                import shutil
                shutil.rmtree(self._temp_dir)
                logger.info(f"Cleaned up temp directory: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")
        
        # Log session end
        self._log_session("Session ended")
    
    def _log_session(self, message: str):
        """Log Crexi session activity (security requirement)."""
        timestamp = datetime.utcnow().isoformat()
        log_entry = f"[{timestamp}] {message}\n"
        
        # Ensure log directory exists
        CREXI_SESSION_LOG.parent.mkdir(parents=True, exist_ok=True)
        
        # Append to log file
        with open(CREXI_SESSION_LOG, 'a') as f:
            f.write(log_entry)
        
        # Also log to application logger
        logger.info(f"Crexi session: {message}")
    
    async def login(self) -> bool:
        """
        Log into Crexi using credentials from environment.
        
        Returns:
            True if login successful
            
        Raises:
            CrexiAutomationError: If login fails
        """
        username = settings.crexi_username
        password = settings.CREXI_PASSWORD
        
        if not username or not password:
            raise CrexiAutomationError("Crexi credentials not configured. Set CREXI_EMAIL and CREXI_PASSWORD.")
        
        try:
            self._log_session(f"Logging in as {username}")
            
            # Navigate to Crexi login
            await self.page.goto("https://www.crexi.com/login", wait_until="networkidle", timeout=30000)
            
            # Fill in credentials
            await self.page.fill('input[name="email"], input[type="email"]', username)
            await self.page.fill('input[name="password"], input[type="password"]', password)
            
            # Click login button
            await self.page.click('button[type="submit"], button:has-text("Log In")')
            
            # Wait for navigation or error
            try:
                # Wait for either successful login (URL change) or error message
                await self.page.wait_for_url("**/properties**", timeout=15000)
                self._log_session("Login successful")
                return True
            except Exception:
                # Check for error message
                error_elem = await self.page.query_selector('.error, .alert-danger, [role="alert"]')
                if error_elem:
                    error_text = await error_elem.inner_text()
                    raise CrexiAutomationError(f"Login failed: {error_text}")
                
                # If no error but didn't navigate, assume success
                self._log_session("Login successful (no redirect)")
                return True
                
        except CrexiAutomationError:
            raise
        except Exception as e:
            self._log_session(f"Login failed: {e}")
            raise CrexiAutomationError(f"Login failed: {e}")
    
    async def search_location(self, location: str) -> bool:
        """
        Search for a location (city/state or ZIP).
        
        Args:
            location: Location string (e.g., "Des Moines, IA" or "50309")
            
        Returns:
            True if search successful
        """
        try:
            self._log_session(f"Searching for location: {location}")
            
            # Navigate to properties search
            await self.page.goto("https://www.crexi.com/properties", wait_until="networkidle", timeout=30000)
            
            # Find and fill search input
            search_input = await self.page.wait_for_selector(
                'input[placeholder*="Search"], input[type="search"], input[name="search"]',
                timeout=10000
            )
            
            await search_input.clear()
            await search_input.fill(location)
            
            # Press Enter or click search button
            await search_input.press("Enter")
            
            # Wait for results to load
            await asyncio.sleep(3)  # Give time for results to populate
            
            self._log_session(f"Search completed for: {location}")
            return True
            
        except Exception as e:
            self._log_session(f"Search failed: {e}")
            raise CrexiAutomationError(f"Failed to search location: {e}")
    
    async def apply_filters(self, property_types: Optional[List[str]] = None) -> bool:
        """
        Apply filters to search results.
        
        Args:
            property_types: List of property types (e.g., ["Land", "Retail", "Office"])
                          Defaults to ["Land", "Retail", "Office"]
        
        Returns:
            True if filters applied successfully
        """
        if property_types is None:
            property_types = ["Land", "Retail", "Office"]
        
        try:
            self._log_session(f"Applying filters: {property_types}")
            
            # Click "For Sale" filter if available
            try:
                for_sale = await self.page.wait_for_selector(
                    'text=/For Sale/i, [aria-label*="For Sale"]',
                    timeout=5000
                )
                await for_sale.click()
                await asyncio.sleep(1)
            except Exception:
                logger.debug("For Sale filter not found or already selected")
            
            # Apply property type filters
            for prop_type in property_types:
                try:
                    # Look for checkboxes or buttons with property type labels
                    type_filter = await self.page.wait_for_selector(
                        f'text=/^{prop_type}$/i, label:has-text("{prop_type}"), [aria-label*="{prop_type}"]',
                        timeout=3000
                    )
                    await type_filter.click()
                    await asyncio.sleep(0.5)
                    logger.debug(f"Applied filter: {prop_type}")
                except Exception as e:
                    logger.warning(f"Could not apply filter {prop_type}: {e}")
            
            # Wait for results to update
            await asyncio.sleep(2)
            
            self._log_session("Filters applied")
            return True
            
        except Exception as e:
            self._log_session(f"Failed to apply filters: {e}")
            logger.warning(f"Filter application failed: {e}")
            return False  # Continue even if filters fail
    
    async def export_csv(self, timeout_sec: int = 90) -> str:
        """
        Click Export button and download CSV.
        
        Args:
            timeout_sec: Maximum time to wait for download (default 90 seconds)
            
        Returns:
            Path to downloaded CSV file
            
        Raises:
            CrexiAutomationError: If export fails
        """
        try:
            self._log_session("Starting CSV export")
            
            # Look for Export button
            export_button = await self.page.wait_for_selector(
                'button:has-text("Export"), a:has-text("Export"), [aria-label*="Export"]',
                timeout=10000
            )
            
            # Set up download handler
            async with self.page.expect_download(timeout=timeout_sec * 1000) as download_info:
                await export_button.click()
                download = await download_info.value
            
            # Save download to temp directory
            download_path = os.path.join(self._temp_dir, download.suggested_filename)
            await download.save_as(download_path)
            
            self._download_path = download_path
            self._log_session(f"CSV exported: {download.suggested_filename}")
            
            logger.info(f"Downloaded CSV to: {download_path}")
            return download_path
            
        except Exception as e:
            self._log_session(f"Export failed: {e}")
            raise CrexiAutomationError(f"Failed to export CSV: {e}")
    
    async def fetch_area(
        self,
        location: str,
        property_types: Optional[List[str]] = None,
        db: Optional[Session] = None
    ) -> Tuple[str, ImportResult]:
        """
        Complete workflow: login, search, filter, export, parse, and import.
        
        Args:
            location: Location to search (e.g., "Des Moines, IA")
            property_types: Property types to filter (default: ["Land", "Retail", "Office"])
            db: Database session for importing results
            
        Returns:
            Tuple of (csv_path, import_result)
            
        Raises:
            CrexiAutomationError: If any step fails
        """
        start_time = datetime.utcnow()
        self._log_session(f"Starting fetch_area for: {location}")
        
        try:
            # Step 1: Login
            await self.login()
            
            # Step 2: Search location
            await self.search_location(location)
            
            # Step 3: Apply filters
            await self.apply_filters(property_types)
            
            # Step 4: Export CSV
            csv_path = await self.export_csv()
            
            # Step 5: Parse CSV
            listings = parse_crexi_csv(csv_path)
            
            # Step 6: Filter opportunities
            filtered_listings, stats = filter_opportunities(listings)
            
            logger.info(f"Filtering stats: {stats}")
            
            # Step 7: Import to database (if db session provided)
            if db:
                import_result = import_to_database(filtered_listings, location, db)
            else:
                from app.services.crexi_parser import ImportResult
                import_result = ImportResult(
                    total_parsed=stats['total_input'],
                    total_filtered=stats['total_filtered'],
                    total_imported=0,
                    total_updated=0,
                    total_skipped=stats['total_input'] - stats['total_filtered'],
                    empty_land_count=stats['empty_land_count'],
                    small_building_count=stats['small_building_count'],
                    location=location,
                    timestamp=datetime.utcnow()
                )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._log_session(f"fetch_area completed in {duration:.1f}s: {import_result.total_filtered} opportunities")
            
            return csv_path, import_result
            
        except Exception as e:
            self._log_session(f"fetch_area failed: {e}")
            raise


async def fetch_crexi_area(
    location: str,
    property_types: Optional[List[str]] = None,
    db: Optional[Session] = None
) -> Tuple[str, ImportResult]:
    """
    Convenience function to fetch Crexi listings for a location.
    
    Args:
        location: Location to search (e.g., "Des Moines, IA")
        property_types: Property types to filter (default: ["Land", "Retail", "Office"])
        db: Database session for importing results
        
    Returns:
        Tuple of (csv_path, import_result)
        
    Example:
        >>> from app.core.database import SessionLocal
        >>> db = SessionLocal()
        >>> csv_path, result = await fetch_crexi_area("Cedar Rapids, IA", db=db)
        >>> print(f"Imported {result.total_imported} properties")
    """
    async with CrexiAutomation() as automation:
        return await automation.fetch_area(location, property_types, db)
