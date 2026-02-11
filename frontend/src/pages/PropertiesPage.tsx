import { Building2, Plus } from 'lucide-react';

export function PropertiesPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Properties</h1>
            <p className="text-sm text-gray-500 mt-1">Track and manage your property pipeline</p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors">
            <Plus className="w-4 h-4" />
            Add Property
          </button>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Building2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No properties yet</h3>
          <p className="text-sm text-gray-500 max-w-md mx-auto">
            Properties will appear here as you approve sites from SCOUT reports, or you can add them manually.
          </p>
        </div>
      </div>
    </div>
  );
}
