/**
 * Listing Links - Generate pre-filled search URLs for external CRE platforms
 *
 * Since commercial property APIs are expensive or unavailable, we generate
 * search URLs that users can click to find active listings on external sites.
 */

export interface ListingLink {
  name: string;
  url: string;
  logo?: string;
  color: string;
}

/**
 * Generate listing search URLs for a given location
 */
export function generateListingLinks(
  city: string,
  state: string,
  lat?: number,
  lng?: number
): ListingLink[] {
  // URL-encode city and state
  const encodedCity = encodeURIComponent(city);
  const encodedState = encodeURIComponent(state);
  const citySlug = city.toLowerCase().replace(/\s+/g, '-');
  const stateSlug = state.toLowerCase();

  const links: ListingLink[] = [
    {
      name: 'Crexi',
      url: `https://www.crexi.com/properties?location=${encodedCity}%2C+${encodedState}&propertyTypes=Retail,Land,Office,Industrial`,
      color: '#1E3A8A', // Dark Blue
    },
    {
      name: 'LoopNet',
      url: `https://www.loopnet.com/search/commercial-real-estate/${citySlug}-${stateSlug}/for-sale/`,
      color: '#DC2626', // Red
    },
    {
      name: 'CommercialCafe',
      url: `https://www.commercialcafe.com/commercial-real-estate/${stateSlug}/${citySlug}/`,
      color: '#059669', // Green
    },
    {
      name: 'CoStar',
      url: `https://www.costar.com/search?location=${encodedCity}%2C%20${encodedState}&forSale=true`,
      color: '#7C3AED', // Purple
    },
  ];

  // Add coordinates-based search if available
  if (lat && lng) {
    links.push({
      name: 'Google Maps',
      url: `https://www.google.com/maps/search/commercial+property+for+sale/@${lat},${lng},14z`,
      color: '#4285F4', // Google Blue
    });
  }

  return links;
}

/**
 * Generate a single LoopNet URL for a specific address
 */
export function generateLoopNetAddressUrl(address: string, city: string, state: string): string {
  const searchQuery = encodeURIComponent(`${address}, ${city}, ${state}`);
  return `https://www.loopnet.com/search/commercial-real-estate/${searchQuery}/for-sale/`;
}

/**
 * Generate a Crexi URL for a specific location
 */
export function generateCrexiUrl(city: string, state: string): string {
  const encodedCity = encodeURIComponent(city);
  const encodedState = encodeURIComponent(state);
  return `https://www.crexi.com/properties?location=${encodedCity}%2C+${encodedState}`;
}
