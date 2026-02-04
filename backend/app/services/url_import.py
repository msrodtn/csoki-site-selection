"""
URL Import Service - Extract listing data from CRE platform URLs.

Intelligently extracts structured data from Crexi, LoopNet, and other
commercial real estate listing URLs using multiple extraction strategies.
"""

import asyncio
import re
import httpx
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class ListingData(BaseModel):
    """Extracted listing data from URL."""
    success: bool
    source: str = Field(description="'crexi', 'loopnet', 'unknown'")
    external_id: Optional[str] = None
    listing_url: str
    
    # Location
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Property details
    property_type: Optional[str] = None
    price: Optional[float] = None
    price_display: Optional[str] = None
    sqft: Optional[float] = None
    lot_size_acres: Optional[float] = None
    year_built: Optional[int] = None
    
    # Listing info
    title: Optional[str] = None
    description: Optional[str] = None
    broker_name: Optional[str] = None
    broker_company: Optional[str] = None
    broker_phone: Optional[str] = None
    broker_email: Optional[str] = None
    
    # Media
    images: List[str] = []
    
    # Metadata
    confidence: float = Field(default=0.0, ge=0.0, le=100.0, description="Confidence score 0-100")
    extraction_method: str = Field(description="How data was extracted")
    error_message: Optional[str] = None
    raw_html: Optional[str] = None  # For debugging


def detect_source(url: str) -> str:
    """Detect which CRE platform the URL is from."""
    parsed = urlparse(url.lower())
    domain = parsed.netloc
    
    if 'crexi.com' in domain:
        return 'crexi'
    elif 'loopnet.com' in domain:
        return 'loopnet'
    elif 'costar.com' in domain:
        return 'costar'
    else:
        return 'unknown'


def extract_crexi_id(url: str) -> Optional[str]:
    """Extract Crexi listing ID from URL."""
    # Crexi URLs: https://www.crexi.com/properties/XXXXXX-...
    match = re.search(r'/properties/([a-zA-Z0-9\-]+)', url)
    return match.group(1) if match else None


def extract_loopnet_id(url: str) -> Optional[str]:
    """Extract LoopNet listing ID from URL."""
    # LoopNet URLs: https://www.loopnet.com/Listing/XXXX-Address/XXXXX/
    match = re.search(r'/Listing/[^/]+/(\d+)', url)
    return match.group(1) if match else None


def parse_price(price_str: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """
    Parse price string to float and display format.
    
    Returns (numeric_price, display_string)
    """
    if not price_str:
        return None, None
    
    # Clean the string
    cleaned = re.sub(r'[,$]', '', price_str.strip())
    
    # Handle "M" for millions, "K" for thousands
    if 'M' in cleaned.upper():
        try:
            num = float(re.sub(r'[^\d.]', '', cleaned))
            return num * 1_000_000, price_str
        except ValueError:
            pass
    elif 'K' in cleaned.upper():
        try:
            num = float(re.sub(r'[^\d.]', '', cleaned))
            return num * 1_000, price_str
        except ValueError:
            pass
    
    # Try direct conversion
    try:
        return float(cleaned), price_str
    except (ValueError, TypeError):
        return None, price_str


def parse_sqft(sqft_str: Optional[str]) -> Optional[float]:
    """Parse square footage string."""
    if not sqft_str:
        return None
    
    # Remove commas and extract number
    cleaned = re.sub(r'[,\s]', '', sqft_str)
    match = re.search(r'([\d.]+)', cleaned)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def parse_acres(acres_str: Optional[str]) -> Optional[float]:
    """Parse acreage string."""
    if not acres_str:
        return None
    
    # Look for patterns like "2.5 AC" or "1.23 Acres"
    match = re.search(r'([\d.]+)\s*(?:ac|acre)', acres_str.lower())
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


async def extract_via_http(url: str) -> ListingData:
    """
    Extract data via simple HTTP request (no JavaScript).
    
    Fast but less reliable for JavaScript-heavy sites.
    """
    source = detect_source(url)
    external_id = None
    
    if source == 'crexi':
        external_id = extract_crexi_id(url)
    elif source == 'loopnet':
        external_id = extract_loopnet_id(url)
    
    result = ListingData(
        success=False,
        source=source,
        external_id=external_id,
        listing_url=url,
        extraction_method="http"
    )
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = await client.get(url, headers=headers, follow_redirects=True)
            
            if response.status_code != 200:
                result.error_message = f"HTTP {response.status_code}"
                return result
            
            html = response.text
            
            # Try common meta tags first (Open Graph, JSON-LD)
            # This works for many sites regardless of platform
            
            # Extract title
            title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if title_match:
                result.title = title_match.group(1).strip()
            
            # Open Graph tags
            og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.IGNORECASE)
            if og_title:
                result.title = og_title.group(1)
            
            og_desc = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.IGNORECASE)
            if og_desc:
                result.description = og_desc.group(1)
            
            # Look for JSON-LD structured data
            jsonld_match = re.search(r'<script\s+type="application/ld\+json">(.+?)</script>', html, re.DOTALL | re.IGNORECASE)
            if jsonld_match:
                try:
                    import json
                    data = json.loads(jsonld_match.group(1))
                    
                    # Extract address if present
                    if isinstance(data, dict):
                        address_data = data.get('address', {})
                        if address_data:
                            result.address = address_data.get('streetAddress')
                            result.city = address_data.get('addressLocality')
                            result.state = address_data.get('addressRegion')
                            result.postal_code = address_data.get('postalCode')
                        
                        # Extract price
                        offers = data.get('offers', {})
                        if offers and 'price' in offers:
                            result.price = float(offers['price'])
                        
                        # Extract lat/lng
                        geo = data.get('geo', {})
                        if geo:
                            result.latitude = geo.get('latitude')
                            result.longitude = geo.get('longitude')
                        
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
            
            # Set confidence based on what we found
            fields_found = sum([
                bool(result.title),
                bool(result.address),
                bool(result.city),
                bool(result.price),
                bool(result.description)
            ])
            result.confidence = min(fields_found * 20, 100)
            result.success = result.confidence >= 40
            
            return result
            
    except Exception as e:
        result.error_message = str(e)
        return result


async def extract_via_playwright(url: str) -> ListingData:
    """
    Extract data via Playwright (browser automation).
    
    More reliable for JavaScript-heavy sites but slower.
    """
    if not PLAYWRIGHT_AVAILABLE:
        result = ListingData(
            success=False,
            source=detect_source(url),
            listing_url=url,
            extraction_method="playwright",
            error_message="Playwright not installed"
        )
        return result
    
    source = detect_source(url)
    external_id = None
    
    if source == 'crexi':
        external_id = extract_crexi_id(url)
    elif source == 'loopnet':
        external_id = extract_loopnet_id(url)
    
    result = ListingData(
        success=False,
        source=source,
        external_id=external_id,
        listing_url=url,
        extraction_method="playwright"
    )
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Platform-specific selectors
                if source == 'crexi':
                    result = await _extract_crexi_playwright(page, result)
                elif source == 'loopnet':
                    result = await _extract_loopnet_playwright(page, result)
                else:
                    result = await _extract_generic_playwright(page, result)
                
            finally:
                await browser.close()
        
        return result
        
    except Exception as e:
        result.error_message = str(e)
        return result


async def _extract_crexi_playwright(page: Page, result: ListingData) -> ListingData:
    """Extract data from Crexi page using Playwright."""
    try:
        # Wait for content to load
        await page.wait_for_load_state("networkidle")
        
        # Extract title
        title_el = await page.query_selector('h1, .property-title, [data-test="property-title"]')
        if title_el:
            result.title = await title_el.inner_text()
        
        # Extract address
        addr_el = await page.query_selector('.property-address, [data-test="property-address"]')
        if addr_el:
            addr_text = await addr_el.inner_text()
            # Parse address
            parts = [p.strip() for p in addr_text.split(',')]
            if parts:
                result.address = parts[0]
                if len(parts) > 1:
                    result.city = parts[1]
                if len(parts) > 2:
                    state_zip = parts[2].strip().split()
                    if state_zip:
                        result.state = state_zip[0]
                        if len(state_zip) > 1:
                            result.postal_code = state_zip[1]
        
        # Extract price
        price_el = await page.query_selector('.asking-price, .price, [data-test="price"]')
        if price_el:
            price_text = await price_el.inner_text()
            result.price, result.price_display = parse_price(price_text)
        
        # Extract property type
        type_el = await page.query_selector('.property-type, [data-test="property-type"]')
        if type_el:
            result.property_type = await type_el.inner_text()
        
        # Extract square footage
        sqft_el = await page.query_selector('text=/\\d+[,\\s]*SF/i')
        if sqft_el:
            sqft_text = await sqft_el.inner_text()
            result.sqft = parse_sqft(sqft_text)
        
        # Extract description
        desc_el = await page.query_selector('.description, .property-description')
        if desc_el:
            result.description = await desc_el.inner_text()
        
        # Extract images
        img_els = await page.query_selector_all('.property-image img, .gallery img')
        images = []
        for img_el in img_els[:10]:  # Limit to 10 images
            src = await img_el.get_attribute('src')
            if src and 'http' in src:
                images.append(src)
        result.images = images
        
        # Calculate confidence
        fields_found = sum([
            bool(result.title),
            bool(result.address),
            bool(result.price),
            bool(result.city),
            bool(result.description)
        ])
        result.confidence = min(fields_found * 20, 100)
        result.success = result.confidence >= 40
        
    except Exception as e:
        result.error_message = f"Crexi extraction failed: {str(e)}"
    
    return result


async def _extract_loopnet_playwright(page: Page, result: ListingData) -> ListingData:
    """Extract data from LoopNet page using Playwright."""
    try:
        await page.wait_for_load_state("networkidle")
        
        # LoopNet-specific selectors (update as needed based on actual HTML)
        title_el = await page.query_selector('h1.property-title, h1[data-testid="property-title"]')
        if title_el:
            result.title = await title_el.inner_text()
        
        addr_el = await page.query_selector('.property-address, [data-testid="property-address"]')
        if addr_el:
            addr_text = await addr_el.inner_text()
            parts = [p.strip() for p in addr_text.split(',')]
            if parts:
                result.address = parts[0]
                if len(parts) > 1:
                    result.city = parts[1]
                if len(parts) > 2:
                    state_zip = parts[2].strip().split()
                    if state_zip:
                        result.state = state_zip[0]
                        if len(state_zip) > 1:
                            result.postal_code = state_zip[1]
        
        price_el = await page.query_selector('.asking-price, .price-value')
        if price_el:
            price_text = await price_el.inner_text()
            result.price, result.price_display = parse_price(price_text)
        
        # Calculate confidence
        fields_found = sum([
            bool(result.title),
            bool(result.address),
            bool(result.price),
            bool(result.city)
        ])
        result.confidence = min(fields_found * 25, 100)
        result.success = result.confidence >= 40
        
    except Exception as e:
        result.error_message = f"LoopNet extraction failed: {str(e)}"
    
    return result


async def _extract_generic_playwright(page: Page, result: ListingData) -> ListingData:
    """Generic extraction for unknown sites."""
    try:
        await page.wait_for_load_state("networkidle")
        
        # Try to extract title
        title = await page.title()
        if title:
            result.title = title
        
        # Try Open Graph tags
        og_title = await page.query_selector('meta[property="og:title"]')
        if og_title:
            result.title = await og_title.get_attribute('content')
        
        og_desc = await page.query_selector('meta[property="og:description"]')
        if og_desc:
            result.description = await og_desc.get_attribute('content')
        
        result.confidence = 20 if result.title else 0
        result.success = result.confidence >= 20
        
    except Exception as e:
        result.error_message = f"Generic extraction failed: {str(e)}"
    
    return result


async def import_from_url(url: str, use_playwright: bool = False) -> ListingData:
    """
    Import listing data from a URL.
    
    Args:
        url: CRE listing URL (Crexi, LoopNet, etc.)
        use_playwright: If True, use browser automation. If False, try HTTP first.
    
    Returns:
        ListingData with extracted information
    """
    # Clean URL
    url = url.strip()
    
    # Validate URL
    if not url.startswith('http'):
        return ListingData(
            success=False,
            source='unknown',
            listing_url=url,
            extraction_method='none',
            error_message="Invalid URL format"
        )
    
    # Try extraction strategies in order
    if use_playwright or detect_source(url) in ['crexi', 'loopnet']:
        # For known platforms, prefer Playwright for accuracy
        result = await extract_via_playwright(url)
        if result.success:
            return result
    
    # Fall back to HTTP (faster, works for some sites)
    result = await extract_via_http(url)
    if result.success:
        return result
    
    # If HTTP failed, try Playwright as last resort
    if not use_playwright:
        result = await extract_via_playwright(url)
    
    return result
