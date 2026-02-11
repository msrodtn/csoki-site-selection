import { Sidebar } from '../components/Sidebar/Sidebar';
import { MapboxMap } from '../components/Map/MapboxMap';
import { AnalysisPanel } from '../components/Analysis/AnalysisPanel';
import { ComparePanel } from '../components/Analysis/ComparePanel';

export function MapPage() {
  return (
    <div className="flex h-full w-full overflow-hidden">
      <Sidebar />
      <div className="flex-1 relative">
        <MapboxMap />
        <AnalysisPanel />
        <ComparePanel />
      </div>
    </div>
  );
}
