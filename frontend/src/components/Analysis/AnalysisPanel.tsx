import { useMemo, useState, useCallback, useRef, useEffect } from 'react';
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
  GripHorizontal,
  Target,
  Bookmark,
  GitCompare,
} from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';
import { analysisApi, storeApi } from '../../services/api';
import type { POICategory, DemographicMetrics } from '../../types/store';
import { POI_CATEGORY_COLORS, POI_CATEGORY_LABELS, BRAND_COLORS, BRAND_LABELS, BRAND_LOGOS, type BrandKey } from '../../types/store';
import { ReportModal } from './ReportModal';

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
    // Nearest Competitors
    nearestCompetitors,
    setNearestCompetitors,
    isNearestCompetitorsLoading,
    setIsNearestCompetitorsLoading,
    // Navigation
    navigateTo,
    // Saved Locations & Compare
    savedLocations,
    addSavedLocation,
    setShowComparePanel,
    // Analyzed store (captured when analysis started, persists even if selectedStore changes)
    analyzedStore,
  } = useMapStore();

  // Collapsible section states
  const [isPOIExpanded, setIsPOIExpanded] = useState(true);
  const [isDemographicsExpanded, setIsDemographicsExpanded] = useState(false);
  const [isCompetitorsExpanded, setIsCompetitorsExpanded] = useState(false);

  // Report modal state
  const [showReportModal, setShowReportModal] = useState(false);

  // Draggable panel state
  const [position, setPosition] = useState({ x: 340, y: 16 }); // Initial position (left-[340px] top-4)
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const panelRef = useRef<HTMLDivElement>(null);

  // Handle drag events
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - dragStartRef.current.x;
      const deltaY = e.clientY - dragStartRef.current.y;

      setPosition((prev) => ({
        x: Math.max(0, prev.x + deltaX),
        y: Math.max(0, prev.y + deltaY),
      }));

      dragStartRef.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX, y: e.clientY };
  };

  // Reset position when panel is shown
  useEffect(() => {
    if (showAnalysisPanel) {
      setPosition({ x: 340, y: 16 });
    }
  }, [showAnalysisPanel]);

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

  // Load nearest competitors on-demand when section is expanded
  const handleCompetitorsExpand = useCallback(async () => {
    const newExpanded = !isCompetitorsExpanded;
    setIsCompetitorsExpanded(newExpanded);

    // Load nearest competitors if expanding and no data yet
    if (newExpanded && !nearestCompetitors && !isNearestCompetitorsLoading && analysisResult) {
      setIsNearestCompetitorsLoading(true);

      try {
        const data = await storeApi.getNearestCompetitors({
          latitude: analysisResult.center_latitude,
          longitude: analysisResult.center_longitude,
        });
        setNearestCompetitors(data);
      } catch (error) {
        console.error('Failed to load nearest competitors:', error);
      } finally {
        setIsNearestCompetitorsLoading(false);
      }
    }
  }, [
    isCompetitorsExpanded,
    nearestCompetitors,
    isNearestCompetitorsLoading,
    analysisResult,
    setIsNearestCompetitorsLoading,
    setNearestCompetitors,
  ]);

  if (!showAnalysisPanel) {
    return null;
  }

  const handleClose = () => {
    setShowAnalysisPanel(false);
    clearAnalysis();
  };

  // State to track if we're preparing the report
  const [isPreparingReport, setIsPreparingReport] = useState(false);

  const handleExportPDF = async () => {
    if (!analysisResult) return;

    setIsPreparingReport(true);

    try {
      // Load demographics and competitors in parallel if needed
      const promises: Promise<void>[] = [];

      if (!demographicsData) {
        promises.push(
          (async () => {
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
          })()
        );
      }

      if (!nearestCompetitors) {
        promises.push(
          (async () => {
            setIsNearestCompetitorsLoading(true);
            try {
              const data = await storeApi.getNearestCompetitors({
                latitude: analysisResult.center_latitude,
                longitude: analysisResult.center_longitude,
              });
              setNearestCompetitors(data);
            } catch (error) {
              console.error('Failed to load nearest competitors:', error);
            } finally {
              setIsNearestCompetitorsLoading(false);
            }
          })()
        );
      }

      // Wait for all data to load
      await Promise.all(promises);

      // Small delay to ensure state updates are applied
      await new Promise((resolve) => setTimeout(resolve, 100));

      setShowReportModal(true);
    } finally {
      setIsPreparingReport(false);
    }
  };

  return (
    <div
      ref={panelRef}
      className="absolute w-80 bg-white rounded-lg shadow-lg z-20 max-h-[calc(100vh-2rem)] flex flex-col"
      style={{
        left: `${position.x}px`,
        top: `${position.y}px`,
      }}
    >
      {/* Header with drag handle */}
      <div className="bg-gradient-to-r from-red-600 to-red-700 rounded-t-lg">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-2">
            <div
              onMouseDown={handleDragStart}
              className="cursor-grab active:cursor-grabbing p-1 -ml-1 hover:bg-white/20 rounded transition-colors"
              title="Drag to move"
            >
              <GripHorizontal className="w-4 h-4 text-white/70" />
            </div>
            <h2 className="text-lg font-semibold text-white">Trade Area Analysis</h2>
          </div>
          <button
            onClick={handleClose}
            className="text-white/80 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Store Info */}
        {analyzedStore && (
          <div className="px-4 pb-3 flex items-center gap-3 border-t border-white/20 pt-3">
            {BRAND_LOGOS[analyzedStore.brand as BrandKey] && (
              <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center flex-shrink-0 shadow-md">
                <img
                  src={BRAND_LOGOS[analyzedStore.brand as BrandKey]}
                  alt={BRAND_LABELS[analyzedStore.brand as BrandKey] || analyzedStore.brand}
                  className="w-7 h-7 object-contain rounded-full"
                />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="text-white font-medium text-sm truncate">
                {analyzedStore.street || 'Unknown Address'}
              </div>
              <div className="text-white/70 text-xs truncate">
                {[analyzedStore.city, analyzedStore.state].filter(Boolean).join(', ')}
              </div>
            </div>
          </div>
        )}
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
                              <div className="bg-gray-50 rounded-lg p-2 col-span-2">
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

                          {/* Employment (from Census Bureau) */}
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
                            <p className="text-[10px] text-gray-400 mt-1">
                              County-level data from Census Bureau
                            </p>
                          </div>

                          {/* Data vintage note */}
                          <p className="text-xs text-gray-400 text-center">
                            Data: Esri {demographicsData.data_vintage}
                            {demographicsData.census_supplemented && ' + Census Bureau'}
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Nearest Competitors Section - Collapsible, loads on-demand */}
            <div className="mb-4 border rounded-lg overflow-hidden">
              <button
                onClick={handleCompetitorsExpand}
                className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  {isCompetitorsExpanded ? (
                    <ChevronDown className="w-4 h-4 text-gray-500" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-500" />
                  )}
                  <Target className="w-4 h-4 text-red-600" />
                  <span className="font-semibold text-gray-700">Nearest Competitors</span>
                </div>
                <span className="text-xs text-gray-400">by brand</span>
              </button>

              {isCompetitorsExpanded && (
                <div className="p-4 border-t">
                  {isNearestCompetitorsLoading && (
                    <div className="flex items-center justify-center py-4">
                      <Loader2 className="w-5 h-5 text-red-600 animate-spin" />
                      <span className="ml-2 text-sm text-gray-600">Finding competitors...</span>
                    </div>
                  )}

                  {nearestCompetitors && !isNearestCompetitorsLoading && (
                    <div className="space-y-2">
                      {nearestCompetitors.competitors.map((competitor) => {
                        const brandKey = competitor.brand as BrandKey;
                        const brandColor = BRAND_COLORS[brandKey] || '#666';
                        const brandLabel = BRAND_LABELS[brandKey] || competitor.brand;
                        const brandLogo = BRAND_LOGOS[brandKey];

                        return (
                          <button
                            key={competitor.brand}
                            onClick={() => {
                              if (competitor.store.latitude && competitor.store.longitude) {
                                navigateTo(competitor.store.latitude, competitor.store.longitude, 15);
                              }
                            }}
                            className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 transition-colors text-left"
                          >
                            <div className="w-7 h-7 rounded-full border border-gray-200 bg-white flex items-center justify-center flex-shrink-0">
                              {brandLogo ? (
                                <img
                                  src={brandLogo}
                                  alt={brandLabel}
                                  className="w-5 h-5 object-contain rounded-full"
                                />
                              ) : (
                                <div
                                  className="w-5 h-5 rounded-full"
                                  style={{ backgroundColor: brandColor }}
                                />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium text-gray-800 truncate">
                                {brandLabel}
                              </div>
                              <div className="text-xs text-gray-500 truncate">
                                {competitor.store.city}, {competitor.store.state}
                              </div>
                            </div>
                            <div className="text-right flex-shrink-0">
                              <div className="text-sm font-semibold text-gray-700">
                                {competitor.distance_miles.toFixed(1)} mi
                              </div>
                            </div>
                          </button>
                        );
                      })}
                      <p className="text-[10px] text-gray-400 mt-2 text-center">
                        Click to navigate to store
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Footer with action buttons */}
      {analysisResult && !isAnalyzing && (
        <div className="p-4 border-t space-y-2">
          {/* Save & Compare buttons */}
          <div className="flex gap-2">
            <button
              onClick={() => {
                const id = `loc-${Date.now()}`;
                // Use brand name if available, otherwise use coordinates
                const name = analyzedStore?.brand || `${analysisResult.center_latitude.toFixed(4)}, ${analysisResult.center_longitude.toFixed(4)}`;
                addSavedLocation({
                  id,
                  name,
                  brand: analyzedStore?.brand,
                  city: analyzedStore?.city || undefined,
                  state: analyzedStore?.state || undefined,
                  latitude: analysisResult.center_latitude,
                  longitude: analysisResult.center_longitude,
                  savedAt: new Date(),
                });
              }}
              className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-2 px-3 rounded-lg transition-colors text-sm"
            >
              <Bookmark className="w-4 h-4" />
              Save for Compare
            </button>
            <button
              onClick={() => setShowComparePanel(true)}
              disabled={savedLocations.length === 0}
              className="flex-1 flex items-center justify-center gap-2 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-300 text-white py-2 px-3 rounded-lg transition-colors text-sm"
            >
              <GitCompare className="w-4 h-4" />
              Compare ({savedLocations.length})
            </button>
          </div>

          {/* Export button */}
          <button
            onClick={handleExportPDF}
            disabled={isPreparingReport}
            className="w-full flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white py-2 px-4 rounded-lg transition-colors"
          >
            {isPreparingReport ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Preparing Report...
              </>
            ) : (
              <>
                <FileDown className="w-4 h-4" />
                Export PDF Report
              </>
            )}
          </button>
        </div>
      )}

      {/* Report Preview Modal */}
      {analysisResult && (
        <ReportModal
          isOpen={showReportModal}
          onClose={() => setShowReportModal(false)}
          analysisResult={analysisResult}
          demographicsData={demographicsData}
          nearestCompetitors={nearestCompetitors}
          locationName={analyzedStore?.brand ? `${BRAND_LABELS[analyzedStore.brand as BrandKey] || analyzedStore.brand} - ${analyzedStore.city}, ${analyzedStore.state}` : undefined}
          locationAddress={analyzedStore?.street || undefined}
        />
      )}
    </div>
  );
}
