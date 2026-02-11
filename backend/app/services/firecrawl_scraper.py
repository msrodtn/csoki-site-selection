"""
Firecrawl Scraper Service - Extract CRE listings via Firecrawl API.

Replaces Playwright-based browser automation for Crexi and LoopNet scraping.
Uses Firecrawl's AI-powered extraction with rotating proxies and anti-bot bypass.

Two modes:
  - Single URL scrape (Phase A): Extract structured data from one listing page
  - Area search (Phase B): Extract all listing cards from search results pages
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import quote

from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.url_import import (
    detect_source,
    extract_crexi_id,
    extract_loopnet_id,
)

logger = logging.getLogger(__name__)

# Lazy import firecrawl — may not be installed
FIRECRAWL_INSTALLED = False
try:
    from firecrawl import Firecrawl as FirecrawlClient
    FIRECRAWL_INSTALLED = True
except ImportError:
    FirecrawlClient = None


# ---------------------------------------------------------------------------
# Pydantic schemas for Firecrawl AI extraction
# ---------------------------------------------------------------------------

class CREListingExtract(BaseModel):
    """Schema for extracting data from a single listing detail page."""
    title: Optional[str] = Field(None, description="Property listing title or name")
    address: Optional[str] = Field(None, description="Street address of the property")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="2-letter US state code (e.g. IA, NE)")
    postal_code: Optional[str] = Field(None, description="ZIP code")
    property_type: Optional[str] = Field(None, description="Property type: retail, land, office, industrial, mixed_use")
    price: Optional[float] = Field(None, description="Asking price in USD as a number with no formatting")
    price_display: Optional[str] = Field(None, description="Price as displayed on the page (e.g. '$1.2M')")
    sqft: Optional[float] = Field(None, description="Building square footage as a number")
    lot_size_acres: Optional[float] = Field(None, description="Lot size in acres as a number")
    year_built: Optional[int] = Field(None, description="Year the building was constructed")
    description: Optional[str] = Field(None, description="Property description text")
    broker_name: Optional[str] = Field(None, description="Listing broker or agent name")
    broker_company: Optional[str] = Field(None, description="Brokerage company name")
    broker_phone: Optional[str] = Field(None, description="Broker phone number")
    broker_email: Optional[str] = Field(None, description="Broker email address")
    images: List[str] = Field(default_factory=list, description="List of property image URLs")
    latitude: Optional[float] = Field(None, description="Property latitude coordinate")
    longitude: Optional[float] = Field(None, description="Property longitude coordinate")


class CRESearchListing(BaseModel):
    """A single listing card extracted from a search results page."""
    title: Optional[str] = Field(None, description="Property title or name")
    address: Optional[str] = Field(None, description="Full street address")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="2-letter US state code")
    property_type: Optional[str] = Field(None, description="Property type: Retail, Land, Office, Industrial")
    price: Optional[float] = Field(None, description="Asking price in USD as a number")
    price_display: Optional[str] = Field(None, description="Price as shown (e.g. '$350,000')")
    sqft: Optional[float] = Field(None, description="Building square footage as a number")
    lot_size_acres: Optional[float] = Field(None, description="Lot size in acres as a number")
    listing_url: Optional[str] = Field(None, description="URL link to the individual listing page")


class CRESearchPageExtract(BaseModel):
    """Schema for extracting all listing cards from a search results page."""
    listings: List[CRESearchListing] = Field(
        default_factory=list,
        description="All property listing cards visible on this search results page"
    )
    total_results: Optional[int] = Field(
        None,
        description="Total number of results shown (e.g. '171 properties found')"
    )
    next_page_url: Optional[str] = Field(
        None,
        description="URL of the next page of results, if pagination exists"
    )


# ---------------------------------------------------------------------------
# Credit tracker (singleton)
# ---------------------------------------------------------------------------

class FirecrawlBudgetExceeded(Exception):
    """Raised when monthly Firecrawl credit budget would be exceeded."""
    pass


class FirecrawlCreditTracker:
    """Track Firecrawl API credit usage to stay within monthly budget."""

    def __init__(self, monthly_budget: int = 400):
        self.monthly_budget = monthly_budget
        self.credits_used = 0
        self.reset_month = datetime.utcnow().month

    def _maybe_reset(self):
        current_month = datetime.utcnow().month
        if current_month != self.reset_month:
            logger.info(f"New month detected — resetting credit tracker (was {self.credits_used})")
            self.credits_used = 0
            self.reset_month = current_month

    def can_spend(self, credits: int = 1) -> bool:
        self._maybe_reset()
        return (self.credits_used + credits) <= self.monthly_budget

    def spend(self, credits: int = 1):
        self._maybe_reset()
        self.credits_used += credits
        logger.debug(f"Firecrawl credit spent: {credits} (total: {self.credits_used}/{self.monthly_budget})")

    @property
    def remaining(self) -> int:
        self._maybe_reset()
        return max(0, self.monthly_budget - self.credits_used)

    def status(self) -> dict:
        self._maybe_reset()
        return {
            "credits_used": self.credits_used,
            "credits_remaining": self.remaining,
            "monthly_budget": self.monthly_budget,
        }


# Module-level singleton
credit_tracker = FirecrawlCreditTracker(
    monthly_budget=settings.FIRECRAWL_MONTHLY_BUDGET
)


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------

class FirecrawlScraperService:
    """Scrape CRE listings using Firecrawl API instead of Playwright."""

    def __init__(self):
        if not FIRECRAWL_INSTALLED:
            raise RuntimeError("firecrawl-py is not installed. Run: pip install firecrawl-py")
        if not settings.FIRECRAWL_API_KEY:
            raise RuntimeError("FIRECRAWL_API_KEY not configured")
        self.client = FirecrawlClient(api_key=settings.FIRECRAWL_API_KEY)
        self.credit_tracker = credit_tracker

    # ----- Phase A: Single URL scrape ----- #

    async def scrape_single_url(self, url: str) -> dict:
        """
        Scrape a single listing URL and return structured data.
        Cost: 1 credit.
        """
        if not self.credit_tracker.can_spend(1):
            raise FirecrawlBudgetExceeded(
                f"Monthly budget of {self.credit_tracker.monthly_budget} credits reached. "
                f"Used: {self.credit_tracker.credits_used}"
            )

        source = detect_source(url)
        external_id = None
        if source == "crexi":
            external_id = extract_crexi_id(url)
        elif source == "loopnet":
            external_id = extract_loopnet_id(url)

        # Firecrawl SDK is synchronous — run in thread to avoid blocking FastAPI
        # v4 SDK: .scrape() returns a Document pydantic model with .json, .markdown, etc.
        result = await asyncio.to_thread(
            self.client.scrape,
            url,
            formats=[
                "markdown",
                {
                    "type": "json",
                    "schema": CREListingExtract.model_json_schema(),
                    "prompt": (
                        "Extract commercial real estate listing details from this page. "
                        "Focus on: property address, price, square footage, lot size in acres, "
                        "property type (retail/land/office/industrial), broker contact info. "
                        "Return numeric values without formatting."
                    ),
                },
            ],
            only_main_content=False,
            timeout=120000,
        )

        self.credit_tracker.spend(1)

        # Document model: result.json (dict), result.markdown (str)
        extracted = _extract_json(result)
        markdown_text = _extract_markdown(result)

        return {
            "success": bool(extracted and any(extracted.values())),
            "source": source,
            "external_id": external_id,
            "listing_url": url,
            "extraction_method": "firecrawl",
            "confidence": _calculate_confidence(extracted),
            "data": extracted,
            "markdown": (markdown_text or "")[:1000],
        }

    # ----- Phase B: Area search ----- #

    async def search_area(
        self,
        city: str,
        state: str,
        sources: Optional[List[str]] = None,
        max_pages: int = 3,
    ) -> List[dict]:
        """
        Search CRE platforms for listings in an area.

        Scrapes search results pages and extracts all listing card data
        directly — no need to click into individual listing pages.

        Cost: ~1 credit per search page (not per listing).
        """
        if sources is None:
            sources = ["crexi", "loopnet"]

        all_listings: List[dict] = []

        for source in sources:
            search_url = _build_search_url(source, city, state)
            if not search_url:
                continue

            try:
                source_listings = await self._scrape_search_pages(
                    search_url, source, city, state, max_pages
                )
                all_listings.extend(source_listings)
                logger.info(
                    f"Firecrawl extracted {len(source_listings)} listings "
                    f"from {source} for {city}, {state}"
                )
            except FirecrawlBudgetExceeded:
                logger.warning("Firecrawl budget exceeded during area search")
                break
            except Exception as e:
                logger.error(f"Firecrawl area search failed for {source}: {e}")
                continue

        return all_listings

    async def _scrape_search_pages(
        self,
        search_url: str,
        source: str,
        city: str,
        state: str,
        max_pages: int,
    ) -> List[dict]:
        """Scrape 1-N search result pages, extracting all listing cards."""
        listings: List[dict] = []
        current_url = search_url

        for page_num in range(max_pages):
            if not self.credit_tracker.can_spend(1):
                raise FirecrawlBudgetExceeded("Budget exceeded")

            logger.info(f"Scraping {source} search page {page_num + 1}: {current_url}")

            result = await asyncio.to_thread(
                self.client.scrape,
                current_url,
                formats=[
                    "markdown",
                    {
                        "type": "json",
                        "schema": CRESearchPageExtract.model_json_schema(),
                        "prompt": (
                            "Extract ALL commercial real estate property listing cards "
                            "from this search results page. For each listing card, extract: "
                            "title, full address, city, state, property type, asking price "
                            "(as a number), square footage (as a number), lot size in acres "
                            "(as a number), and the URL link to the individual listing. "
                            "Also find the URL for the next page of results if one exists."
                        ),
                    },
                ],
                only_main_content=False,
                timeout=120000,
            )

            self.credit_tracker.spend(1)

            # Document model: result.json (dict with listings, total_results, next_page_url)
            extracted = _extract_json(result)
            markdown_text = _extract_markdown(result)
            page_listings = extracted.get("listings", [])

            logger.info(f"Page {page_num + 1} result type: {type(result).__name__}")
            logger.info(f"Page {page_num + 1} extracted: {extracted}")
            logger.info(f"Page {page_num + 1} markdown preview ({len(markdown_text)} chars): {markdown_text[:500]}")
            logger.info(f"Page {page_num + 1} found {len(page_listings)} listing cards")

            if not page_listings:
                logger.info(f"No listings found on page {page_num + 1} — stopping pagination")
                break

            for listing_data in page_listings:
                # Ensure it's a dict (Firecrawl may return Pydantic-like objects)
                if hasattr(listing_data, "dict"):
                    listing_data = listing_data.dict()
                elif hasattr(listing_data, "model_dump"):
                    listing_data = listing_data.model_dump()

                # Extract external ID from listing URL
                listing_url = listing_data.get("listing_url", "")
                external_id = None
                if listing_url:
                    if source == "crexi":
                        external_id = extract_crexi_id(listing_url)
                    elif source == "loopnet":
                        external_id = extract_loopnet_id(listing_url)

                listings.append({
                    "success": True,
                    "source": source,
                    "external_id": external_id,
                    "listing_url": listing_url,
                    "extraction_method": "firecrawl",
                    "confidence": _calculate_confidence(listing_data),
                    "data": {
                        **listing_data,
                        "city": listing_data.get("city") or city,
                        "state": listing_data.get("state") or state,
                    },
                })

            # Check for next page
            next_url = extracted.get("next_page_url")
            if not next_url:
                logger.info(f"No next page URL found — stopping after page {page_num + 1}")
                break
            current_url = next_url

        return listings


# ---------------------------------------------------------------------------
# Geocoding backfill
# ---------------------------------------------------------------------------

async def backfill_coordinates(listing_data: dict) -> dict:
    """
    Geocode address if lat/lng missing from Firecrawl extraction.

    Uses the existing Nominatim-based GeocodingService.
    Critical: listings without coordinates won't appear on the map.
    """
    if listing_data.get("latitude") and listing_data.get("longitude"):
        return listing_data

    address = listing_data.get("address", "")
    city = listing_data.get("city", "")
    state = listing_data.get("state", "")

    if not (city and state):
        return listing_data

    try:
        from app.services.geocoding import GeocodingService

        geocoder = GeocodingService()
        coords = await asyncio.to_thread(
            geocoder.geocode_address,
            address or "",
            city,
            state,
            listing_data.get("postal_code", ""),
        )
        if coords:
            listing_data["latitude"] = coords[0]
            listing_data["longitude"] = coords[1]
            logger.debug(f"Geocoded {address}, {city}, {state} → {coords}")
        else:
            logger.warning(f"Geocoding failed for: {address}, {city}, {state}")
    except Exception as e:
        logger.warning(f"Geocoding error: {e}")

    return listing_data


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def normalize_property_type(type_str: Optional[str]) -> Optional[str]:
    """Normalize property type to standard values."""
    if not type_str:
        return None
    t = type_str.lower()
    if any(x in t for x in ["retail", "shop", "store", "restaurant"]):
        return "retail"
    elif any(x in t for x in ["land", "vacant", "lot"]):
        return "land"
    elif "office" in t:
        return "office"
    elif any(x in t for x in ["industrial", "warehouse", "manufacturing"]):
        return "industrial"
    elif any(x in t for x in ["mixed", "multi"]):
        return "mixed_use"
    return "unknown"


def firecrawl_to_crexi_listing(result: dict):
    """
    Convert a Firecrawl extraction result to a CrexiListing dataclass
    so the existing filter_opportunities() pipeline works unchanged.
    """
    from app.services.crexi_parser import CrexiListing

    data = result.get("data", {})
    return CrexiListing(
        property_link=result.get("listing_url", ""),
        property_name=data.get("title", ""),
        property_status="Active",
        property_type=data.get("property_type", ""),
        address=data.get("address"),
        city=data.get("city", ""),
        state=data.get("state", ""),
        zip_code=data.get("postal_code"),
        tenant=None,
        lease_term=None,
        remaining_term=None,
        sqft=data.get("sqft"),
        lot_size_acres=data.get("lot_size_acres"),
        units=None,
        price_per_unit=None,
        noi=None,
        cap_rate=None,
        asking_price=data.get("price"),
        price_per_sqft=None,
        price_per_acre=None,
        days_on_market=None,
        opportunity_zone=None,
        longitude=data.get("longitude"),
        latitude=data.get("latitude"),
    )


def firecrawl_result_to_scraped_listing(
    result: dict,
    search_city: Optional[str] = None,
    search_state: Optional[str] = None,
) -> dict:
    """
    Convert Firecrawl extraction result to a dict matching ScrapedListing columns.
    """
    data = result.get("data", {})
    prop_type = normalize_property_type(data.get("property_type"))

    return {
        "source": result.get("source", "unknown"),
        "external_id": result.get("external_id"),
        "listing_url": result.get("listing_url"),
        "address": data.get("address"),
        "city": data.get("city") or search_city,
        "state": data.get("state") or search_state,
        "postal_code": data.get("postal_code"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "property_type": prop_type,
        "price": data.get("price"),
        "price_display": data.get("price_display") or (
            f"${data['price']:,.0f}" if data.get("price") else None
        ),
        "sqft": data.get("sqft"),
        "lot_size_acres": data.get("lot_size_acres"),
        "year_built": data.get("year_built"),
        "title": data.get("title"),
        "description": data.get("description"),
        "broker_name": data.get("broker_name"),
        "broker_company": data.get("broker_company"),
        "broker_phone": data.get("broker_phone"),
        "broker_email": data.get("broker_email"),
        "images": data.get("images", []),
        "raw_data": {
            "extraction_method": "firecrawl",
            "confidence": result.get("confidence", 0),
            "search_page_extraction": result.get("extraction_method") == "firecrawl",
        },
        "search_city": search_city or data.get("city"),
        "search_state": search_state or data.get("state"),
        "is_active": True,
        "last_verified": datetime.utcnow(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(result) -> dict:
    """
    Extract the JSON/structured data from a Firecrawl Document response.
    The v4 SDK returns a Document pydantic model with .json attribute.
    """
    if result is None:
        return {}
    # If it's already a dict (unlikely in v4 but defensive)
    if isinstance(result, dict):
        return result.get("json", {}) or {}
    # Pydantic Document model — access .json attribute
    if hasattr(result, "json") and result.json is not None:
        # result.json could be a dict or a pydantic model
        val = result.json
        if isinstance(val, dict):
            return val
        if hasattr(val, "model_dump"):
            return val.model_dump()
        if hasattr(val, "dict"):
            return val.dict()
        return {}
    # Try model_dump as fallback
    if hasattr(result, "model_dump"):
        dump = result.model_dump()
        return dump.get("json", {}) or {}
    return {}


def _extract_markdown(result) -> str:
    """Extract markdown text from a Firecrawl Document response."""
    if result is None:
        return ""
    if isinstance(result, dict):
        return result.get("markdown", "") or ""
    if hasattr(result, "markdown"):
        return result.markdown or ""
    return ""


def _build_search_url(source: str, city: str, state: str) -> Optional[str]:
    """Build search URL for a CRE platform (mirrors listingLinks.ts patterns)."""
    if source == "crexi":
        encoded = quote(f"{city}, {state}")
        return (
            f"https://www.crexi.com/properties"
            f"?location={encoded}"
            f"&propertyTypes=Retail,Land,Office,Industrial"
            f"&sort=newest"
        )
    elif source == "loopnet":
        city_slug = city.lower().replace(" ", "-")
        state_slug = state.lower()
        return (
            f"https://www.loopnet.com/search/commercial-real-estate"
            f"/{city_slug}-{state_slug}/for-sale/"
        )
    return None


def _calculate_confidence(extracted: dict) -> float:
    """Calculate extraction confidence based on key fields populated."""
    if not extracted:
        return 0.0
    key_fields = [
        "title", "address", "city", "price", "property_type", "sqft", "lot_size_acres"
    ]
    found = sum(1 for f in key_fields if extracted.get(f))
    return round(min(found / len(key_fields) * 100, 100), 1)


def is_firecrawl_available() -> bool:
    """Check if Firecrawl service can be used."""
    return FIRECRAWL_INSTALLED and bool(settings.FIRECRAWL_API_KEY)
