import { useState, useRef, useCallback } from 'react';
import { X, Download, Loader2, Eye } from 'lucide-react';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import { TradeAreaReport } from './TradeAreaReport';
import type {
  TradeAreaAnalysis,
  DemographicsResponse,
  NearestCompetitorsResponse,
} from '../../types/store';

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  analysisResult: TradeAreaAnalysis;
  demographicsData: DemographicsResponse | null;
  nearestCompetitors: NearestCompetitorsResponse | null;
  locationName?: string;
  locationAddress?: string;
}

export function ReportModal({
  isOpen,
  onClose,
  analysisResult,
  demographicsData,
  nearestCompetitors,
  locationName,
  locationAddress,
}: ReportModalProps) {
  const [isExporting, setIsExporting] = useState(false);
  const reportRef = useRef<HTMLDivElement>(null);

  const handleExportPDF = useCallback(async () => {
    if (!reportRef.current) return;

    setIsExporting(true);

    try {
      // Wait for charts to render
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Capture the report as canvas
      const canvas = await html2canvas(reportRef.current, {
        scale: 2, // Higher quality
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
        windowWidth: 900,
      });

      // Calculate PDF dimensions (A4 proportions)
      const imgWidth = 210; // A4 width in mm
      const pageHeight = 297; // A4 height in mm
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      // Create PDF
      const pdf = new jsPDF('p', 'mm', 'a4');
      let heightLeft = imgHeight;
      let position = 0;

      // Add first page
      pdf.addImage(
        canvas.toDataURL('image/png'),
        'PNG',
        0,
        position,
        imgWidth,
        imgHeight,
        undefined,
        'FAST'
      );
      heightLeft -= pageHeight;

      // Add additional pages if needed
      while (heightLeft >= 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(
          canvas.toDataURL('image/png'),
          'PNG',
          0,
          position,
          imgWidth,
          imgHeight,
          undefined,
          'FAST'
        );
        heightLeft -= pageHeight;
      }

      // Generate filename
      const timestamp = new Date().toISOString().split('T')[0];
      const safeName = (locationName || 'trade-area')
        .replace(/[^a-z0-9]/gi, '-')
        .toLowerCase();
      const filename = `${safeName}-analysis-${timestamp}.pdf`;

      pdf.save(filename);
    } catch (error) {
      console.error('Failed to export PDF:', error);
      alert('Failed to export PDF. Please try again.');
    } finally {
      setIsExporting(false);
    }
  }, [locationName]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-2xl max-w-5xl w-full max-h-[90vh] flex flex-col m-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-3">
            <Eye className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-semibold text-gray-900">Report Preview</h2>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleExportPDF}
              disabled={isExporting}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white px-4 py-2 rounded-lg transition-colors text-sm font-medium"
            >
              {isExporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating PDF...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Download PDF
                </>
              )}
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Report Preview */}
        <div className="flex-1 overflow-auto bg-gray-100 p-6">
          <div className="shadow-lg">
            <TradeAreaReport
              ref={reportRef}
              analysisResult={analysisResult}
              demographicsData={demographicsData}
              nearestCompetitors={nearestCompetitors}
              locationName={locationName}
              locationAddress={locationAddress}
            />
          </div>
        </div>

        {/* Footer hint */}
        <div className="px-6 py-3 border-t bg-gray-50 text-center text-xs text-gray-500">
          Scroll to preview full report • Click "Download PDF" to save
        </div>
      </div>
    </div>
  );
}
