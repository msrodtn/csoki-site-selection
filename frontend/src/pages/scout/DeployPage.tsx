import { useState } from 'react';
import { Rocket, Info } from 'lucide-react';

const MARKETS = [
  { code: 'IA', name: 'Iowa', cities: 'Des Moines, Cedar Rapids, Davenport' },
  { code: 'NE', name: 'Nebraska', cities: 'Omaha, Lincoln, Bellevue' },
  { code: 'NV', name: 'Nevada', cities: 'Las Vegas, Reno, Henderson' },
  { code: 'ID', name: 'Idaho', cities: 'Boise, Meridian, Nampa' },
];

export function DeployPage() {
  const [selectedMarket, setSelectedMarket] = useState('');
  const [scope, setScope] = useState<'full' | 'custom'>('full');
  const [isDeploying, setIsDeploying] = useState(false);

  const handleDeploy = () => {
    setIsDeploying(true);
    // TODO: Call API to create job
    setTimeout(() => setIsDeploying(false), 2000);
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-gray-900">Deploy Analysis</h1>
          <p className="text-sm text-gray-500 mt-1">Configure and launch a new SCOUT analysis job</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
          {/* Market Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Target Market</label>
            <div className="grid grid-cols-2 gap-3">
              {MARKETS.map((market) => (
                <button
                  key={market.code}
                  onClick={() => setSelectedMarket(market.code)}
                  className={`text-left p-4 rounded-lg border-2 transition-all ${
                    selectedMarket === market.code
                      ? 'border-red-500 bg-red-50'
                      : 'border-gray-200 hover:border-gray-300 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-900">{market.name}</span>
                    <span className="text-xs font-mono text-gray-400">{market.code}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{market.cities}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Scope */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Analysis Scope</label>
            <div className="flex gap-3">
              <button
                onClick={() => setScope('full')}
                className={`flex-1 p-3 rounded-lg border-2 text-sm transition-all ${
                  scope === 'full'
                    ? 'border-red-500 bg-red-50 text-red-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <span className="font-medium">Full Market Scan</span>
                <p className="text-xs mt-0.5 opacity-70">Analyze all candidate sites in the market</p>
              </button>
              <button
                onClick={() => setScope('custom')}
                className={`flex-1 p-3 rounded-lg border-2 text-sm transition-all ${
                  scope === 'custom'
                    ? 'border-red-500 bg-red-50 text-red-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300'
                }`}
              >
                <span className="font-medium">Custom Bounds</span>
                <p className="text-xs mt-0.5 opacity-70">Define specific geographic area</p>
              </button>
            </div>
          </div>

          {/* Config summary */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <Info className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-gray-600">
                <p className="font-medium text-gray-700 mb-1">Analysis Configuration</p>
                <ul className="space-y-0.5 text-xs">
                  <li>Config: <span className="font-mono">csoki</span> (Verizon criteria)</li>
                  <li>Agents: Feasibility, Regulatory, Sentiment, Growth, Planning, Verification</li>
                  <li>Est. time: ~4 hours for full market scan</li>
                  <li>Concurrent agents: 4</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Deploy button */}
          <button
            onClick={handleDeploy}
            disabled={!selectedMarket || isDeploying}
            className={`w-full flex items-center justify-center gap-2 px-6 py-3 rounded-lg text-sm font-medium transition-all ${
              selectedMarket && !isDeploying
                ? 'bg-red-600 text-white hover:bg-red-700'
                : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
          >
            <Rocket className="w-4 h-4" />
            {isDeploying ? 'Deploying...' : 'Launch Analysis'}
          </button>
        </div>
      </div>
    </div>
  );
}
