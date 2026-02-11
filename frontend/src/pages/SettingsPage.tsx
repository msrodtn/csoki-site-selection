import { Settings } from 'lucide-react';

export function SettingsPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
          <p className="text-sm text-gray-500 mt-1">Configure your platform preferences</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Settings className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Coming soon</h3>
          <p className="text-sm text-gray-500 max-w-md mx-auto">
            Settings for API keys, SCOUT agent configuration, notifications, and user management will be available here.
          </p>
        </div>
      </div>
    </div>
  );
}
