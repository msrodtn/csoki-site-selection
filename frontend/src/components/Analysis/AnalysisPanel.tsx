import { useMemo } from 'react';
import { X, Eye, EyeOff, FileDown, MapPin, Store, Utensils, ShoppingBag, Loader2 } from 'lucide-react';
import { useMapStore } from '../../store/useMapStore';
import type { POICategory } from '../../types/store';
import { POI_CATEGORY_COLORS, POI_CATEGORY_LABELS } from '../../types/store';

const CATEGORY_ICONS: Record<POICategory, React.ReactNode> = {
  anchors: <Store className="w-4 h-4" />,
  quick_service: <MapPin className="w-4 h-4" />,
  restaurants: <Utensils className="w-4 h-4" />,
  retail: <ShoppingBag className="w-4 h-4" />,
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
  } = useMapStore();

  const visibleCategoriesArray = useMemo(
    () => Array.from(visiblePOICategories),
    [visiblePOICategories]
  );

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

    // Summary section
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

    // POI Details section
    yPos += 20;
    doc.setFontSize(14);
    doc.setTextColor(227, 24, 55);
    doc.text('POI Details', 20, yPos);

    doc.setFontSize(9);
    doc.setTextColor(0);
    yPos += 10;

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

        {analysisResult && !isAnalyzing && (
          <>
            {/* Location Info */}
            <div className="mb-4 text-sm text-gray-600">
              <p>
                <span className="font-medium">Radius:</span>{' '}
                {(analysisResult.radius_meters / 1609.34).toFixed(1)} miles
              </p>
            </div>

            {/* POI Category Toggles */}
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">POI Categories</h3>
              <div className="space-y-2">
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
            </div>

            {/* Total count */}
            <div className="bg-gray-50 rounded-lg p-3 mb-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700">Total POIs</span>
                <span className="text-lg font-bold text-red-600">
                  {Object.values(analysisResult.summary).reduce((a, b) => a + b, 0)}
                </span>
              </div>
            </div>

            {/* Top POIs list */}
            {analysisResult.pois.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-gray-700 mb-2">
                  Top Locations ({Math.min(10, analysisResult.pois.length)} of{' '}
                  {analysisResult.pois.length})
                </h3>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {analysisResult.pois
                    .filter((poi) => visibleCategoriesArray.includes(poi.category))
                    .slice(0, 10)
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
