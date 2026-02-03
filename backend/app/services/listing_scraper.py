"""
Listing Scraper Service - Browser automation for CRE platforms.

Uses Playwright to scrape commercial property listings from Crexi and LoopNet
using the user's own authenticated credentials. For internal business use only.
"""

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ScrapedProperty:
    """Normalized property data from scraping."""
    source: str
    external_id: Optional[str]
    listing_url: Optional[str]
    address: Optional[str]
    city: str
    state: str
    postal_code: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    property_type: Optional[str]
    price: Optional[float]
    price_display: Optional[str]
    sqft: Optional[float]
    lot_size_acres: Optional[float]
    year_built: Optional[int]
    title: Optional[str]
    description: Optional[str]
    broker_name: Optional[str]
    broker_company: Optional[str]
    broker_phone: Optional[str]
    broker_email: Optional[str]
    images: list[str]
    raw_data: dict


class BaseScraper(ABC):
    """Base class for listing scrapers."""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    @abstractmethod
    async def login(self) -> bool:
        """Login to the platform. Returns True if successful."""
        pass

    @abstractmethod
    async def search(self, city: str, state: str, property_types: list[str] = None) -> list[ScrapedProperty]:
        """Search for listings in the given location."""
        pass

    async def setup(self, headless: bool = True):
        """Initialize browser and page."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=headless)
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()

    async def cleanup(self):
        """Clean up browser resources."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    def parse_price(self, price_str: str) -> tuple[Optional[float], str]:
        """Parse price string to float and display format."""
        if not price_str:
            return None, "Contact for Pricing"

        price_str = price_str.strip()
        display = price_str

        # Remove currency symbols and commas
        cleaned = re.sub(r'[,$]', '', price_str)

        # Handle "M" for millions, "K" for thousands
        multiplier = 1
        if 'M' in cleaned.upper():
            multiplier = 1_000_000
            cleaned = re.sub(r'[Mm]', '', cleaned)
        elif 'K' in cleaned.upper():
            multiplier = 1_000
            cleaned = re.sub(r'[Kk]', '', cleaned)

        try:
            value = float(re.sub(r'[^\d.]', '', cleaned)) * multiplier
            return value, display
        except (ValueError, TypeError):
            return None, display

    def parse_sqft(self, sqft_str: str) -> Optional[float]:
        """Parse square footage string to float."""
        if not sqft_str:
            return None
        try:
            cleaned = re.sub(r'[,\s]', '', sqft_str)
            cleaned = re.sub(r'(sf|sqft|sq\.?\s*ft\.?)', '', cleaned, flags=re.IGNORECASE)
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def parse_acres(self, acres_str: str) -> Optional[float]:
        """Parse acreage string to float."""
        if not acres_str:
            return None
        try:
            cleaned = re.sub(r'(acres?|ac\.?)', '', acres_str, flags=re.IGNORECASE)
            cleaned = re.sub(r'[,\s]', '', cleaned)
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def normalize_property_type(self, type_str: str) -> str:
        """Normalize property type to standard values."""
        if not type_str:
            return "unknown"

        type_lower = type_str.lower()

        if any(x in type_lower for x in ['retail', 'shop', 'store', 'restaurant']):
            return "retail"
        elif any(x in type_lower for x in ['land', 'vacant', 'lot']):
            return "land"
        elif any(x in type_lower for x in ['office']):
            return "office"
        elif any(x in type_lower for x in ['industrial', 'warehouse', 'manufacturing']):
            return "industrial"
        elif any(x in type_lower for x in ['mixed', 'multi']):
            return "mixed_use"
        else:
            return "unknown"


class CrexiScraper(BaseScraper):
    """Scraper for Crexi.com commercial listings."""

    BASE_URL = "https://www.crexi.com"
    LOGIN_URL = "https://www.crexi.com/login"

    async def login(self) -> bool:
        """Login to Crexi with credentials."""
        username = settings.CREXI_USERNAME
        password = settings.CREXI_PASSWORD

        if not username or not password:
            logger.error("Crexi credentials not configured")
            return False

        try:
            await self.page.goto(self.LOGIN_URL)
            await self.page.wait_for_load_state("networkidle")

            # Fill login form
            await self.page.fill('input[name="email"], input[type="email"]', username)
            await self.page.fill('input[name="password"], input[type="password"]', password)

            # Submit and wait for navigation
            await self.page.click('button[type="submit"]')
            await self.page.wait_for_load_state("networkidle")

            # Check if login was successful (look for dashboard or profile element)
            await asyncio.sleep(2)
            is_logged_in = await self.page.locator('[data-testid="user-menu"], .user-avatar, .profile-icon').count() > 0

            if is_logged_in:
                logger.info("Successfully logged into Crexi")
                return True
            else:
                logger.warning("Crexi login may have failed - continuing anyway")
                return True  # Some features work without login

        except Exception as e:
            logger.error(f"Error logging into Crexi: {e}")
            return False

    async def search(self, city: str, state: str, property_types: list[str] = None) -> list[ScrapedProperty]:
        """Search Crexi for commercial listings."""
        if property_types is None:
            property_types = ["Retail", "Land", "Office", "Industrial"]

        properties = []
        type_param = ",".join(property_types)
        location = f"{city}, {state}"
        encoded_location = quote(location)

        search_url = f"{self.BASE_URL}/properties?location={encoded_location}&propertyTypes={type_param}&sort=newest"

        try:
            logger.info(f"Searching Crexi: {search_url}")
            await self.page.goto(search_url)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)  # Allow dynamic content to load

            # Wait for listing cards to appear
            await self.page.wait_for_selector('.property-card, [data-testid="property-card"]', timeout=10000)

            # Get all listing cards
            cards = await self.page.locator('.property-card, [data-testid="property-card"]').all()
            logger.info(f"Found {len(cards)} listings on Crexi")

            for card in cards[:50]:  # Limit to 50 results
                try:
                    prop = await self._parse_crexi_card(card, city, state)
                    if prop:
                        properties.append(prop)
                except Exception as e:
                    logger.warning(f"Error parsing Crexi listing: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error searching Crexi: {e}")

        return properties

    async def _parse_crexi_card(self, card, search_city: str, search_state: str) -> Optional[ScrapedProperty]:
        """Parse a Crexi property card element."""
        try:
            # Extract data from card
            title_el = card.locator('.property-title, h3, .title')
            title = await title_el.first.text_content() if await title_el.count() > 0 else None

            address_el = card.locator('.property-address, .address')
            address = await address_el.first.text_content() if await address_el.count() > 0 else None

            price_el = card.locator('.property-price, .price')
            price_text = await price_el.first.text_content() if await price_el.count() > 0 else None
            price, price_display = self.parse_price(price_text)

            type_el = card.locator('.property-type, .type')
            type_text = await type_el.first.text_content() if await type_el.count() > 0 else None
            property_type = self.normalize_property_type(type_text)

            sqft_el = card.locator('.property-sqft, .sqft, .size')
            sqft_text = await sqft_el.first.text_content() if await sqft_el.count() > 0 else None
            sqft = self.parse_sqft(sqft_text)

            # Get listing URL
            link_el = card.locator('a[href*="/properties/"]')
            listing_url = None
            external_id = None
            if await link_el.count() > 0:
                href = await link_el.first.get_attribute('href')
                if href:
                    listing_url = f"{self.BASE_URL}{href}" if not href.startswith('http') else href
                    # Extract ID from URL
                    match = re.search(r'/properties/(\d+)', href)
                    if match:
                        external_id = match.group(1)

            # Get image
            images = []
            img_el = card.locator('img')
            if await img_el.count() > 0:
                img_src = await img_el.first.get_attribute('src')
                if img_src and not img_src.startswith('data:'):
                    images.append(img_src)

            return ScrapedProperty(
                source="crexi",
                external_id=external_id,
                listing_url=listing_url,
                address=address.strip() if address else None,
                city=search_city,
                state=search_state,
                postal_code=None,
                latitude=None,
                longitude=None,
                property_type=property_type,
                price=price,
                price_display=price_display,
                sqft=sqft,
                lot_size_acres=None,
                year_built=None,
                title=title.strip() if title else None,
                description=None,
                broker_name=None,
                broker_company=None,
                broker_phone=None,
                broker_email=None,
                images=images,
                raw_data={
                    "title": title,
                    "address": address,
                    "price_text": price_text,
                    "type_text": type_text,
                    "sqft_text": sqft_text,
                }
            )

        except Exception as e:
            logger.warning(f"Error parsing Crexi card: {e}")
            return None


class LoopNetScraper(BaseScraper):
    """Scraper for LoopNet.com commercial listings."""

    BASE_URL = "https://www.loopnet.com"
    LOGIN_URL = "https://www.loopnet.com/profile/Account/Login"

    async def login(self) -> bool:
        """Login to LoopNet with credentials."""
        username = settings.LOOPNET_USERNAME
        password = settings.LOOPNET_PASSWORD

        if not username or not password:
            logger.error("LoopNet credentials not configured")
            return False

        try:
            await self.page.goto(self.LOGIN_URL)
            await self.page.wait_for_load_state("networkidle")

            # Fill login form
            await self.page.fill('#Email, input[name="Email"]', username)
            await self.page.fill('#Password, input[name="Password"]', password)

            # Submit and wait for navigation
            await self.page.click('button[type="submit"], input[type="submit"]')
            await self.page.wait_for_load_state("networkidle")

            await asyncio.sleep(2)
            logger.info("Submitted LoopNet login")
            return True

        except Exception as e:
            logger.error(f"Error logging into LoopNet: {e}")
            return False

    async def search(self, city: str, state: str, property_types: list[str] = None) -> list[ScrapedProperty]:
        """Search LoopNet for commercial listings."""
        properties = []

        # LoopNet uses city-state slug format
        city_slug = city.lower().replace(' ', '-')
        state_slug = state.lower()

        search_url = f"{self.BASE_URL}/search/commercial-real-estate/{city_slug}-{state_slug}/for-sale/"

        try:
            logger.info(f"Searching LoopNet: {search_url}")
            await self.page.goto(search_url)
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            # Wait for listings to load
            await self.page.wait_for_selector('.placard, .listing-card, article', timeout=10000)

            # Get all listing cards
            cards = await self.page.locator('.placard, .listing-card, article.listing').all()
            logger.info(f"Found {len(cards)} listings on LoopNet")

            for card in cards[:50]:  # Limit to 50 results
                try:
                    prop = await self._parse_loopnet_card(card, city, state)
                    if prop:
                        properties.append(prop)
                except Exception as e:
                    logger.warning(f"Error parsing LoopNet listing: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error searching LoopNet: {e}")

        return properties

    async def _parse_loopnet_card(self, card, search_city: str, search_state: str) -> Optional[ScrapedProperty]:
        """Parse a LoopNet property card element."""
        try:
            # Extract data from card
            title_el = card.locator('.placard-header-link, .listing-title, h2')
            title = await title_el.first.text_content() if await title_el.count() > 0 else None

            address_el = card.locator('.placard-address, .listing-address, .address')
            address = await address_el.first.text_content() if await address_el.count() > 0 else None

            price_el = card.locator('.placard-price, .listing-price, .price')
            price_text = await price_el.first.text_content() if await price_el.count() > 0 else None
            price, price_display = self.parse_price(price_text)

            type_el = card.locator('.placard-type, .property-type, .type')
            type_text = await type_el.first.text_content() if await type_el.count() > 0 else None
            property_type = self.normalize_property_type(type_text)

            # Size can be sqft or acres
            size_el = card.locator('.placard-sf, .listing-size, .size')
            size_text = await size_el.first.text_content() if await size_el.count() > 0 else None
            sqft = None
            acres = None
            if size_text:
                if 'acre' in size_text.lower():
                    acres = self.parse_acres(size_text)
                else:
                    sqft = self.parse_sqft(size_text)

            # Get listing URL
            link_el = card.locator('a[href*="/Listing/"]')
            listing_url = None
            external_id = None
            if await link_el.count() > 0:
                href = await link_el.first.get_attribute('href')
                if href:
                    listing_url = f"{self.BASE_URL}{href}" if not href.startswith('http') else href
                    # Extract ID from URL
                    match = re.search(r'/Listing/(\d+)', href)
                    if match:
                        external_id = match.group(1)

            # Get image
            images = []
            img_el = card.locator('img')
            if await img_el.count() > 0:
                img_src = await img_el.first.get_attribute('src')
                if img_src and not img_src.startswith('data:'):
                    images.append(img_src)

            return ScrapedProperty(
                source="loopnet",
                external_id=external_id,
                listing_url=listing_url,
                address=address.strip() if address else None,
                city=search_city,
                state=search_state,
                postal_code=None,
                latitude=None,
                longitude=None,
                property_type=property_type,
                price=price,
                price_display=price_display,
                sqft=sqft,
                lot_size_acres=acres,
                year_built=None,
                title=title.strip() if title else None,
                description=None,
                broker_name=None,
                broker_company=None,
                broker_phone=None,
                broker_email=None,
                images=images,
                raw_data={
                    "title": title,
                    "address": address,
                    "price_text": price_text,
                    "type_text": type_text,
                    "size_text": size_text,
                }
            )

        except Exception as e:
            logger.warning(f"Error parsing LoopNet card: {e}")
            return None


class ListingScraperService:
    """
    Main service for scraping listings from multiple platforms.

    Usage:
        service = ListingScraperService()
        results = await service.search_all("Des Moines", "IA")
    """

    def __init__(self):
        self.crexi = CrexiScraper()
        self.loopnet = LoopNetScraper()

    async def search_crexi(
        self,
        city: str,
        state: str,
        property_types: list[str] = None,
        headless: bool = True
    ) -> list[ScrapedProperty]:
        """Search only Crexi."""
        try:
            await self.crexi.setup(headless=headless)
            await self.crexi.login()
            return await self.crexi.search(city, state, property_types)
        finally:
            await self.crexi.cleanup()

    async def search_loopnet(
        self,
        city: str,
        state: str,
        property_types: list[str] = None,
        headless: bool = True
    ) -> list[ScrapedProperty]:
        """Search only LoopNet."""
        try:
            await self.loopnet.setup(headless=headless)
            await self.loopnet.login()
            return await self.loopnet.search(city, state, property_types)
        finally:
            await self.loopnet.cleanup()

    async def search_all(
        self,
        city: str,
        state: str,
        property_types: list[str] = None,
        headless: bool = True,
        sources: list[str] = None
    ) -> dict[str, list[ScrapedProperty]]:
        """
        Search all configured platforms.

        Args:
            city: City name
            state: 2-letter state code
            property_types: List of property types to search
            headless: Run browser without GUI
            sources: Specific sources to search ['crexi', 'loopnet']

        Returns:
            Dict mapping source name to list of properties
        """
        if sources is None:
            sources = ['crexi', 'loopnet']

        results = {}

        if 'crexi' in sources:
            try:
                results['crexi'] = await self.search_crexi(city, state, property_types, headless)
            except Exception as e:
                logger.error(f"Crexi search failed: {e}")
                results['crexi'] = []

        if 'loopnet' in sources:
            try:
                results['loopnet'] = await self.search_loopnet(city, state, property_types, headless)
            except Exception as e:
                logger.error(f"LoopNet search failed: {e}")
                results['loopnet'] = []

        return results


# Convenience function for quick searches
async def search_listings(
    city: str,
    state: str,
    sources: list[str] = None,
    property_types: list[str] = None
) -> dict[str, list[ScrapedProperty]]:
    """
    Quick search function for listings.

    Example:
        results = await search_listings("Des Moines", "IA")
    """
    service = ListingScraperService()
    return await service.search_all(city, state, property_types, headless=True, sources=sources)
