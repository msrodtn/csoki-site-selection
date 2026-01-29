import { forwardRef } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  MapPin,
  Users,
  DollarSign,
  Briefcase,
  ShoppingCart,
  Target,
} from 'lucide-react';
import type {
  TradeAreaAnalysis,
  DemographicsResponse,
  NearestCompetitorsResponse,
  POICategory,
} from '../../types/store';
import {
  POI_CATEGORY_COLORS,
  POI_CATEGORY_LABELS,
  BRAND_COLORS,
  BRAND_LABELS,
  type BrandKey,
} from '../../types/store';

interface TradeAreaReportProps {
  analysisResult: TradeAreaAnalysis;
  demographicsData: DemographicsResponse | null;
  nearestCompetitors: NearestCompetitorsResponse | null;
  locationName?: string;
  locationAddress?: string;
}

// Format numbers with commas
const formatNumber = (num: number | null): string => {
  if (num === null || num === undefined) return 'N/A';
  return num.toLocaleString();
};

// Format currency
const formatCurrency = (num: number | null): string => {
  if (num === null || num === undefined) return 'N/A';
  if (num >= 1000000) return '$' + (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return '$' + (num / 1000).toFixed(0) + 'K';
  return '$' + num.toLocaleString();
};

// Format compact number
const formatCompact = (num: number | null): string => {
  if (num === null || num === undefined) return 'N/A';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString();
};

export const TradeAreaReport = forwardRef<HTMLDivElement, TradeAreaReportProps>(
  ({ analysisResult, demographicsData, nearestCompetitors, locationName, locationAddress }, ref) => {
    const radiusMiles = (analysisResult.radius_meters / 1609.34).toFixed(1);

    // POI data for pie chart
    const poiData = (['anchors', 'quick_service', 'restaurants', 'retail'] as POICategory[])
      .map((category) => ({
        name: POI_CATEGORY_LABELS[category],
        value: analysisResult.summary[category] || 0,
        color: POI_CATEGORY_COLORS[category],
      }))
      .filter((d) => d.value > 0);

    const totalPOIs = poiData.reduce((sum, d) => sum + d.value, 0);

    // Demographics data for charts
    const populationData = demographicsData?.radii.map((r) => ({
      radius: `${r.radius_miles} mi`,
      population: r.total_population,
      households: r.total_households,
    })) || [];

    const incomeData = demographicsData?.radii.map((r) => ({
      radius: `${r.radius_miles} mi`,
      median: r.median_household_income,
      average: r.average_household_income,
    })) || [];

    const spendingData = demographicsData?.radii.map((r) => ({
      radius: `${r.radius_miles} mi`,
      retail: r.spending_retail_total,
      food: r.spending_food_away,
      entertainment: r.spending_entertainment,
    })) || [];

    // Get 1-mile demographics for key metrics
    const demo1Mile = demographicsData?.radii.find((r) => r.radius_miles === 1);

    return (
      <div
        ref={ref}
        className="bg-white p-8 max-w-4xl mx-auto"
        style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}
      >
        {/* Header */}
        <div className="border-b-4 border-red-600 pb-6 mb-8">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-1">
                Trade Area Analysis Report
              </h1>
              <p className="text-gray-500 text-sm">
                Generated {new Date().toLocaleDateString('en-US', {
                  weekday: 'long',
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                })}
              </p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-red-600">CSOKi</div>
              <div className="text-xs text-gray-400">Site Selection Platform</div>
            </div>
          </div>

          {/* Location Info */}
          <div className="mt-6 bg-gray-50 rounded-xl p-4 flex items-center gap-6">
            <div className="bg-red-600 rounded-full p-3">
              <MapPin className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <div className="text-lg font-semibold text-gray-900">
                {locationName || `${analysisResult.center_latitude.toFixed(4)}, ${analysisResult.center_longitude.toFixed(4)}`}
              </div>
              {locationAddress && (
                <div className="text-gray-500 text-sm">{locationAddress}</div>
              )}
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-red-600">{radiusMiles}</div>
              <div className="text-gray-500 text-sm">mile radius</div>
            </div>
          </div>
        </div>

        {/* Key Metrics Row */}
        {demo1Mile && (
          <div className="grid grid-cols-4 gap-4 mb-8">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-4 text-white">
              <Users className="w-6 h-6 mb-2 opacity-80" />
              <div className="text-2xl font-bold">{formatCompact(demo1Mile.total_population)}</div>
              <div className="text-blue-100 text-sm">Population (1mi)</div>
            </div>
            <div className="bg-gradient-to-br from-emerald-500 to-emerald-600 rounded-xl p-4 text-white">
              <DollarSign className="w-6 h-6 mb-2 opacity-80" />
              <div className="text-2xl font-bold">{formatCurrency(demo1Mile.median_household_income)}</div>
              <div className="text-emerald-100 text-sm">Median HH Income</div>
            </div>
            <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-xl p-4 text-white">
              <Briefcase className="w-6 h-6 mb-2 opacity-80" />
              <div className="text-2xl font-bold">{formatCompact(demo1Mile.total_businesses)}</div>
              <div className="text-orange-100 text-sm">Businesses (1mi)</div>
            </div>
            <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-4 text-white">
              <ShoppingCart className="w-6 h-6 mb-2 opacity-80" />
              <div className="text-2xl font-bold">{formatCurrency(demo1Mile.spending_retail_total)}</div>
              <div className="text-purple-100 text-sm">Retail Spending</div>
            </div>
          </div>
        )}

        {/* Two Column Layout */}
        <div className="grid grid-cols-2 gap-8 mb-8">
          {/* POI Summary */}
          <div className="border rounded-xl p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <MapPin className="w-5 h-5 text-purple-600" />
              Points of Interest
            </h2>

            <div className="flex items-center gap-4">
              <div className="w-40 h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={poiData}
                      cx="50%"
                      cy="50%"
                      innerRadius={35}
                      outerRadius={60}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {poiData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value) => [value ?? 0, 'Count']}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="flex-1 space-y-2">
                {(['anchors', 'quick_service', 'restaurants', 'retail'] as POICategory[]).map(
                  (category) => {
                    const count = analysisResult.summary[category] || 0;
                    const percentage = totalPOIs > 0 ? ((count / totalPOIs) * 100).toFixed(0) : 0;
                    return (
                      <div key={category} className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: POI_CATEGORY_COLORS[category] }}
                        />
                        <span className="text-sm text-gray-600 flex-1">
                          {POI_CATEGORY_LABELS[category]}
                        </span>
                        <span className="text-sm font-semibold text-gray-900">{count}</span>
                        <span className="text-xs text-gray-400 w-10 text-right">{percentage}%</span>
                      </div>
                    );
                  }
                )}
                <div className="border-t pt-2 mt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">Total POIs</span>
                    <span className="text-lg font-bold text-purple-600">{totalPOIs}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Top POIs */}
            {analysisResult.pois.length > 0 && (
              <div className="mt-4 pt-4 border-t">
                <h3 className="text-sm font-semibold text-gray-500 uppercase mb-2">
                  Notable Locations
                </h3>
                <div className="space-y-1">
                  {analysisResult.pois.slice(0, 5).map((poi) => (
                    <div
                      key={poi.place_id}
                      className="flex items-center gap-2 text-sm"
                    >
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: POI_CATEGORY_COLORS[poi.category] }}
                      />
                      <span className="text-gray-700 truncate flex-1">{poi.name}</span>
                      {poi.rating && (
                        <span className="text-yellow-500 text-xs">{poi.rating}★</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Nearest Competitors */}
          <div className="border rounded-xl p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-red-600" />
              Nearest Competitors
            </h2>

            {nearestCompetitors ? (
              <div className="space-y-3">
                {nearestCompetitors.competitors.map((competitor) => {
                  const brandKey = competitor.brand as BrandKey;
                  const brandColor = BRAND_COLORS[brandKey] || '#666';
                  const brandLabel = BRAND_LABELS[brandKey] || competitor.brand;
                  const maxDistance = Math.max(
                    ...nearestCompetitors.competitors.map((c) => c.distance_miles)
                  );
                  const barWidth = (competitor.distance_miles / maxDistance) * 100;

                  return (
                    <div key={competitor.brand}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: brandColor }}
                          />
                          <span className="text-sm font-medium text-gray-700">
                            {brandLabel}
                          </span>
                        </div>
                        <span className="text-sm font-semibold text-gray-900">
                          {competitor.distance_miles.toFixed(1)} mi
                        </span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${barWidth}%`,
                            backgroundColor: brandColor,
                          }}
                        />
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">
                        {competitor.store.city}, {competitor.store.state}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center text-gray-400 py-8">
                Competitor data not loaded
              </div>
            )}
          </div>
        </div>

        {/* Demographics Section */}
        {demographicsData && (
          <div className="border rounded-xl p-6 mb-8">
            <h2 className="text-lg font-bold text-gray-900 mb-6 flex items-center gap-2">
              <Users className="w-5 h-5 text-blue-600" />
              Demographics by Radius
              <span className="text-xs font-normal text-gray-400 ml-2">
                Source: Esri {demographicsData.data_vintage}
              </span>
            </h2>

            <div className="grid grid-cols-3 gap-6">
              {/* Population Chart */}
              <div>
                <h3 className="text-sm font-semibold text-gray-600 mb-3 text-center">
                  Population & Households
                </h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={populationData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="radius" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={formatCompact} />
                    <Tooltip
                      formatter={(value) => formatNumber(value as number | null)}
                      contentStyle={{ fontSize: 12 }}
                    />
                    <Bar dataKey="population" fill="#3B82F6" name="Population" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="households" fill="#93C5FD" name="Households" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Income Chart */}
              <div>
                <h3 className="text-sm font-semibold text-gray-600 mb-3 text-center">
                  Household Income
                </h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={incomeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="radius" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={formatCurrency} />
                    <Tooltip
                      formatter={(value) => formatCurrency(value as number | null)}
                      contentStyle={{ fontSize: 12 }}
                    />
                    <Bar dataKey="median" fill="#10B981" name="Median" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="average" fill="#6EE7B7" name="Average" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Spending Chart */}
              <div>
                <h3 className="text-sm font-semibold text-gray-600 mb-3 text-center">
                  Consumer Spending
                </h3>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={spendingData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="radius" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={formatCurrency} />
                    <Tooltip
                      formatter={(value) => formatCurrency(value as number | null)}
                      contentStyle={{ fontSize: 12 }}
                    />
                    <Bar dataKey="retail" fill="#8B5CF6" name="Retail" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="food" fill="#C4B5FD" name="Food" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Demographics Data Table */}
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 text-gray-500 font-medium">Metric</th>
                    {demographicsData.radii.map((r) => (
                      <th key={r.radius_miles} className="text-right py-2 text-gray-500 font-medium">
                        {r.radius_miles} Mile
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b">
                    <td className="py-2 text-gray-700">Population</td>
                    {demographicsData.radii.map((r) => (
                      <td key={r.radius_miles} className="text-right py-2 font-medium">
                        {formatNumber(r.total_population)}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 text-gray-700">Households</td>
                    {demographicsData.radii.map((r) => (
                      <td key={r.radius_miles} className="text-right py-2 font-medium">
                        {formatNumber(r.total_households)}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 text-gray-700">Median Age</td>
                    {demographicsData.radii.map((r) => (
                      <td key={r.radius_miles} className="text-right py-2 font-medium">
                        {r.median_age?.toFixed(1) || 'N/A'}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 text-gray-700">Median HH Income</td>
                    {demographicsData.radii.map((r) => (
                      <td key={r.radius_miles} className="text-right py-2 font-medium">
                        {formatCurrency(r.median_household_income)}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 text-gray-700">Per Capita Income</td>
                    {demographicsData.radii.map((r) => (
                      <td key={r.radius_miles} className="text-right py-2 font-medium">
                        {formatCurrency(r.per_capita_income)}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="py-2 text-gray-700">Total Businesses</td>
                    {demographicsData.radii.map((r) => (
                      <td key={r.radius_miles} className="text-right py-2 font-medium">
                        {formatNumber(r.total_businesses)}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="py-2 text-gray-700">Total Employees</td>
                    {demographicsData.radii.map((r) => (
                      <td key={r.radius_miles} className="text-right py-2 font-medium">
                        {formatNumber(r.total_employees)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="border-t pt-4 mt-8 flex items-center justify-between text-xs text-gray-400">
          <div>
            CSOKi Site Selection Platform - Confidential
          </div>
          <div>
            Coordinates: {analysisResult.center_latitude.toFixed(6)}, {analysisResult.center_longitude.toFixed(6)}
          </div>
        </div>
      </div>
    );
  }
);

TradeAreaReport.displayName = 'TradeAreaReport';
