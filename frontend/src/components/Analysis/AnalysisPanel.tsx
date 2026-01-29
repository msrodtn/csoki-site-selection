import { useMemo, useState, useCallback } from 'react';
import {
  X,
  Eye,
  EyeOff,
  FileDown,
  MapPin,
  Store,
  Utensils,
  ShoppingBag,
  Loader2,
  ChevronDown,
  ChevronRight,
  Users,
  DollarSign,
  Briefcase,
  ShoppingCart,
} from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';
import { analysisApi } from '../../services/api';
import type { POICategory, DemographicMetrics } from '../../types/store';
import { POI_CATEGORY_COLORS, POI_CATEGORY_LABELS } from '../../types/store';

const RADIUS_OPTIONS = [
  { value: 0.25, label: '0.25 mi' },
  { value: 0.5, label: '0.5 mi' },
  { value: 1, label: '1 mi' },
  { value: 2, label: '2 mi' },
  { value: 3, label: '3 mi' },
];

const DEMOGRAPHICS_RADII = [
  { value: 1, label: '1 mi' },
  { value: 3, label: '3 mi' },
  { value: 5, label: '5 mi' },
];

const CATEGORY_ICONS: Record<POICategory, React.ReactNode> = {
  anchors: <Store className="w-4 h-4" />,
  quick_service: <MapPin className="w-4 h-4" />,
  restaurants: <Utensils className="w-4 h-4" />,
  retail: <ShoppingBag className="w-4 h-4" />,
};

// Format numbers with commas
const formatNumber = (num: number | null): string => {
  if (num === null) return 'N/A';
  return num.toLocaleString();
};

// Format currency
const formatCurrency = (num: number | null): string => {
  if (num === null) return 'N/A';
  return '$' + num.toLocaleString();
};

// Format density
const formatDensity = (num: number | null): string => {
  if (num === null) return 'N/A';
  return num.toLocaleString(undefined, { maximumFractionDigits: 0 }) + '/sq mi';
};

export function AnalysisPanel() {
  const {
    analysisResult,
    isAnalyzing,
    analysisError,
    showAnalysisPanel,
    setShowAnalysisPanel,
    visiblePOICategories,
    togglePOICategory,
    clearAnalysis,
    analysisRadius,
    setAnalysisRadius,
    // Demographics
    demographicsData,
    setDemographicsData,
    isDemographicsLoading,
    setIsDemographicsLoading,
    demographicsError,
    setDemographicsError,
    selectedDemographicsRadius,
    setSelectedDemographicsRadius,
  } = useMapStore();

  // Collapsible section states
  const [isPOIExpanded, setIsPOIExpanded] = useState(true);
  const [isDemographicsExpanded, setIsDemographicsExpanded] = useState(false);

  const visibleCategoriesArray = useMemo(
    () => Array.from(visiblePOICategories),
    [visiblePOICategories]
  );

  // Load demographics on-demand when section is expanded
  const handleDemographicsExpand = useCallback(async () => {
    const newExpanded = !isDemographicsExpanded;
    setIsDemographicsExpanded(newExpanded);

    // Load demographics if expanding and no data yet
    if (newExpanded && !demographicsData && !isDemographicsLoading && analysisResult) {
      setIsDemographicsLoading(true);
      setDemographicsError(null);

      try {
        const data = await analysisApi.getDemographics({
          latitude: analysisResult.center_latitude,
          longitude: analysisResult.center_longitude,
        });
        setDemographicsData(data);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to load demographics';
        setDemographicsError(message);
      } finally {
        setIsDemographicsLoading(false);
      }
    }
  }, [
    isDemographicsExpanded,
    demographicsData,
    isDemographicsLoading,
    analysisResult,
    setIsDemographicsLoading,
    setDemographicsError,
    setDemographicsData,
  ]);

  // Get current demographics metrics for selected radius
  const currentDemographics: DemographicMetrics | null = useMemo(() => {
    if (!demographicsData) return null;
    return demographicsData.radii.find((r) => r.radius_miles === selectedDemographicsRadius) || null;
  }, [demographicsData, selectedDemographicsRadius]);

  if (!showAnalysisPanel) {
    return null;
  }

  const handleClose = () => {
    setShowAnalysisPanel(false);
    clearAnalysis();
  };

  const handleExportPDF = async () => {
    if (!analysisResult) return;

    // Dynamic import of jsPDF to avoid bundle bloat
    const { default: jsPDF } = await import('jspdf');
    const doc = new jsPDF();

    const centerLat = analysisResult.center_latitude.toFixed(4);
    const centerLng = analysisResult.center_longitude.toFixed(4);
    const radiusMiles = (analysisResult.radius_meters / 1609.34).toFixed(1);

    // Title
    doc.setFontSize(20);
    doc.setTextColor(227, 24, 55); // CSOKi red
    doc.text('Trade Area Analysis Report', 20, 20);

    // Subtitle with date
    doc.setFontSize(10);
    doc.setTextColor(100);
    doc.text(`Generated: ${new Date().toLocaleString()}`, 20, 28);

    // Location info
    doc.setFontSize(12);
    doc.setTextColor(0);
    doc.text(`Location: ${centerLat}, ${centerLng}`, 20, 40);
    doc.text(`Radius: ${radiusMiles} miles`, 20, 48);

    // POI Summary section
    doc.setFontSize(14);
    doc.setTextColor(227, 24, 55);
    doc.text('POI Summary', 20, 62);

    doc.setFontSize(11);
    doc.setTextColor(0);
    let yPos = 72;
    const categories: POICategory[] = ['anchors', 'quick_service', 'restaurants', 'retail'];

    categories.forEach((category) => {
      const count = analysisResult.summary[category] || 0;
      const label = POI_CATEGORY_LABELS[category];
      doc.text(`${label}: ${count}`, 25, yPos);
      yPos += 8;
    });

    const totalPOIs = Object.values(analysisResult.summary).reduce((a, b) => a + b, 0);
    doc.setFontSize(12);
    doc.text(`Total POIs: ${totalPOIs}`, 20, yPos + 5);
    yPos += 15;

    // Demographics section (if available)
    if (demographicsData) {
      doc.setFontSize(14);
      doc.setTextColor(227, 24, 55);
      doc.text('Demographics (ArcGIS)', 20, yPos);
      yPos += 10;

      demographicsData.radii.forEach((metrics) => {
        doc.setFontSize(11);
        doc.setTextColor(60);
        doc.text(`${metrics.radius_miles} Mile Radius:`, 20, yPos);
        yPos += 7;

        doc.setFontSize(9);
        doc.setTextColor(0);
        doc.text(`Population: ${formatNumber(metrics.total_population)}`, 25, yPos);
        yPos += 5;
        doc.text(`Households: ${formatNumber(metrics.total_households)}`, 25, yPos);
        yPos += 5;
        doc.text(`Median HH Income: ${formatCurrency(metrics.median_household_income)}`, 25, yPos);
        yPos += 5;
        doc.text(`Businesses: ${formatNumber(metrics.total_businesses)}`, 25, yPos);
        yPos += 5;
        doc.text(`Total Retail Spending: ${formatCurrency(metrics.spending_retail_total)}`, 25, yPos);
        yPos += 10;

        if (yPos > 260) {
          doc.addPage();
          yPos = 20;
        }
      });
    }

    // POI Details section
    if (yPos > 200) {
      doc.addPage();
      yPos = 20;
    }

    doc.setFontSize(14);
    doc.setTextColor(227, 24, 55);
    doc.text('POI Details', 20, yPos);
    yPos += 10;

    doc.setFontSize(9);
    doc.setTextColor(0);

    // Group POIs by category
    categories.forEach((category) => {
      const categoryPOIs = analysisResult.pois.filter((p) => p.category === category);
      if (categoryPOIs.length === 0) return;

      doc.setFontSize(11);
      doc.setTextColor(60);
      doc.text(POI_CATEGORY_LABELS[category], 20, yPos);
      yPos += 6;

      doc.setFontSize(9);
      doc.setTextColor(0);

      categoryPOIs.slice(0, 15).forEach((poi) => {
        if (yPos > 270) {
          doc.addPage();
          yPos = 20;
        }
        const ratingText = poi.rating ? ` (${poi.rating} stars)` : '';
        doc.text(`- ${poi.name}${ratingText}`, 25, yPos);
        yPos += 5;
      });

      if (categoryPOIs.length > 15) {
        doc.text(`  ... and ${categoryPOIs.length - 15} more`, 25, yPos);
        yPos += 5;
      }

      yPos += 5;
    });

    // Footer
    doc.setFontSize(8);
    doc.setTextColor(150);
    doc.text('CSOKi Site Selection Platform - Confidential', 20, 285);

    // Save the PDF
    doc.save(`trade-area-analysis-${Date.now()}.pdf`);
  };

  return (
    <div className="absolute top-4 left-[340px] w-80 bg-white rounded-lg shadow-lg z-20 max-h-[calc(100vh-2rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-gradient-to-r from-red-600 to-red-700 rounded-t-lg">
        <h2 className="text-lg font-semibold text-white">Trade Area Analysis</h2>
        <button
          onClick={handleClose}
          className="text-white/80 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {isAnalyzing && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-8 h-8 text-red-600 animate-spin" />
            <span className="ml-2 text-gray-600">Analyzing area...</span>
          </div>
        )}

        {analysisError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {analysisError}
          </div>
        )}

        {/* Radius Selector - always visible */}
        <div className="mb-4">
          <label className="text-sm font-semibold text-gray-700 mb-2 block">
            Analysis Radius
          </label>
          <div className="relative">
            <select
              value={analysisRadius}
              onChange={(e) => setAnalysisRadius(Number(e.target.value))}
              className="w-full appearance-none bg-gray-100 border border-gray-200 rounded-lg px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
            >
              {RADIUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
          </div>
        </div>

        {analysisResult && !isAnalyzing && (
          <>
            {/* POI Section - Collapsible */}
            <div className="mb-4 border rounded-lg overflow-hidden">
              <button
                onClick={() => setIsPOIExpanded(!isPOIExpanded)}
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {isPOIExpanded ? (
                    <ChevronDown className="w-4 h-4 text-gray-500" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-500" />
                  )}
                  <MapPin className="w-4 h-4 text-purple-600" />
                  <span className="font-semibold text-gray-700">Points of Interest</span>
                </div>
                <span className="text-sm font-medium text-gray-500">
                  {Object.values(analysisResult.summary).reduce((a, b) => a + b, 0)} total
                </span>
              </button>

              {isPOIExpanded && (
                <div className="p-4 border-t">
                  {/* POI Category Toggles */}
                  <div className="space-y-2 mb-4">
                    {(['anchors', 'quick_service', 'restaurants', 'retail'] as POICategory[]).map(
                      (category) => {
                        const isVisible = visibleCategoriesArray.includes(category);
                        const count = analysisResult.summary[category] || 0;

                        return (
                          <button
                            key={category}
                            onClick={() => togglePOICategory(category)}
                            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${
                              isVisible
                                ? 'bg-gray-100 hover:bg-gray-200'
                                : 'bg-gray-50 text-gray-400 hover:bg-gray-100'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <div
                                className="w-3 h-3 rounded-full"
                                style={{
                                  backgroundColor: isVisible
                                    ? POI_CATEGORY_COLORS[category]
                                    : '#ccc',
                                }}
                              />
                              {CATEGORY_ICONS[category]}
                              <span className="text-sm">{POI_CATEGORY_LABELS[category]}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium">{count}</span>
                              {isVisible ? (
                                <Eye className="w-4 h-4 text-gray-500" />
                              ) : (
                                <EyeOff className="w-4 h-4 text-gray-400" />
                              )}
                            </div>
                          </button>
                        );
                      }
                    )}
                  </div>

                  {/* Top POIs list */}
                  {analysisResult.pois.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                        Top Locations
                      </h4>
                      <div className="space-y-1 max-h-32 overflow-y-auto">
                        {analysisResult.pois
                          .filter((poi) => visibleCategoriesArray.includes(poi.category))
                          .slice(0, 8)
                          .map((poi) => (
                            <div
                              key={poi.place_id}
                              className="flex items-center gap-2 text-sm py-1 px-2 hover:bg-gray-50 rounded"
                            >
                              <div
                                className="w-2 h-2 rounded-full flex-shrink-0"
                                style={{ backgroundColor: POI_CATEGORY_COLORS[poi.category] }}
                              />
                              <span className="truncate flex-1">{poi.name}</span>
                              {poi.rating && (
                                <span className="text-xs text-gray-400">{poi.rating}★</span>
                              )}
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Demographics Section - Collapsible, loads on-demand */}
            <div className="mb-4 border rounded-lg overflow-hidden">
              <button
                onClick={handleDemographicsExpand}
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {isDemographicsExpanded ? (
                    <ChevronDown className="w-4 h-4 text-gray-500" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-500" />
                  )}
                  <Users className="w-4 h-4 text-blue-600" />
                  <span className="font-semibold text-gray-700">Demographics</span>
                </div>
                <span className="text-xs text-gray-400">ArcGIS</span>
              </button>

              {isDemographicsExpanded && (
                <div className="p-4 border-t">
                  {isDemographicsLoading && (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
                      <span className="ml-2 text-sm text-gray-600">Loading demographics...</span>
                    </div>
                  )}

                  {demographicsError && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                      {demographicsError}
                    </div>
                  )}

                  {demographicsData && !isDemographicsLoading && (
                    <>
                      {/* Radius Toggle */}
                      <div className="flex gap-1 mb-4">
                        {DEMOGRAPHICS_RADII.map((radius) => (
                          <button
                            key={radius.value}
                            onClick={() => setSelectedDemographicsRadius(radius.value)}
                            className={`flex-1 py-1.5 px-2 text-sm rounded-lg transition-colors ${
                              selectedDemographicsRadius === radius.value
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                          >
                            {radius.label}
                          </button>
                        ))}
                      </div>

                      {currentDemographics && (
                        <div className="space-y-4">
                          {/* Population */}
                          <div>
                            <div className="flex items-center gap-2 mb-2">
                              <Users className="w-4 h-4 text-green-600" />
                              <span className="text-xs font-semibold text-gray-500 uppercase">
                                Population
                              </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                              <div className="bg-gray-50 rounded-lg p-2">
                                <div className="text-gray-500 text-xs">Total Pop.</div>
                                <div className="font-semibold">
                                  {formatNumber(currentDemographics.total_population)}
                                </div>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2">
                                <div className="text-gray-500 text-xs">Households</div>
                                <div className="font-semibold">
                                  {formatNumber(currentDemographics.total_households)}
                                </div>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2">
                                <div className="text-gray-500 text-xs">Density</div>
                                <div className="font-semibold">
                                  {formatDensity(currentDemographics.population_density)}
                                </div>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2">
                                <div className="text-gray-500 text-xs">Median Age</div>
                                <div className="font-semibold">
                                  {currentDemographics.median_age?.toFixed(1) || 'N/A'}
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Income */}
                          <div>
                            <div className="flex items-center gap-2 mb-2">
                              <DollarSign className="w-4 h-4 text-emerald-600" />
                              <span className="text-xs font-semibold text-gray-500 uppercase">
                                Income
                              </span>
                            </div>
                            <div className="grid grid-cols-1 gap-2 text-sm">
                              <div className="bg-gray-50 rounded-lg p-2 flex justify-between">
                                <span className="text-gray-500">Median HH Income</span>
                                <span className="font-semibold">
                                  {formatCurrency(currentDemographics.median_household_income)}
                                </span>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2 flex justify-between">
                                <span className="text-gray-500">Avg HH Income</span>
                                <span className="font-semibold">
                                  {formatCurrency(currentDemographics.average_household_income)}
                                </span>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2 flex justify-between">
                                <span className="text-gray-500">Per Capita Income</span>
                                <span className="font-semibold">
                                  {formatCurrency(currentDemographics.per_capita_income)}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Employment */}
                          <div>
                            <div className="flex items-center gap-2 mb-2">
                              <Briefcase className="w-4 h-4 text-orange-600" />
                              <span className="text-xs font-semibold text-gray-500 uppercase">
                                Employment
                              </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                              <div className="bg-gray-50 rounded-lg p-2">
                                <div className="text-gray-500 text-xs">Businesses</div>
                                <div className="font-semibold">
                                  {formatNumber(currentDemographics.total_businesses)}
                                </div>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2">
                                <div className="text-gray-500 text-xs">Employees</div>
                                <div className="font-semibold">
                                  {formatNumber(currentDemographics.total_employees)}
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Consumer Spending */}
                          <div>
                            <div className="flex items-center gap-2 mb-2">
                              <ShoppingCart className="w-4 h-4 text-purple-600" />
                              <span className="text-xs font-semibold text-gray-500 uppercase">
                                Consumer Spending
                              </span>
                            </div>
                            <div className="grid grid-cols-1 gap-2 text-sm">
                              <div className="bg-gray-50 rounded-lg p-2 flex justify-between">
                                <span className="text-gray-500">Retail Total</span>
                                <span className="font-semibold text-purple-700">
                                  {formatCurrency(currentDemographics.spending_retail_total)}
                                </span>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2 flex justify-between">
                                <span className="text-gray-500">Food Away</span>
                                <span className="font-semibold">
                                  {formatCurrency(currentDemographics.spending_food_away)}
                                </span>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2 flex justify-between">
                                <span className="text-gray-500">Apparel</span>
                                <span className="font-semibold">
                                  {formatCurrency(currentDemographics.spending_apparel)}
                                </span>
                              </div>
                              <div className="bg-gray-50 rounded-lg p-2 flex justify-between">
                                <span className="text-gray-500">Entertainment</span>
                                <span className="font-semibold">
                                  {formatCurrency(currentDemographics.spending_entertainment)}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Data vintage note */}
                          <p className="text-xs text-gray-400 text-center">
                            Data: Esri {demographicsData.data_vintage}
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Footer with Export button */}
      {analysisResult && !isAnalyzing && (
        <div className="p-4 border-t">
          <button
            onClick={handleExportPDF}
            className="w-full flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white py-2 px-4 rounded-lg transition-colors"
          >
            <FileDown className="w-4 h-4" />
            Export PDF Report
          </button>
        </div>
      )}
    </div>
  );
}
