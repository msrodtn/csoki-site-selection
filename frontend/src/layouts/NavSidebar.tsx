import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Map,
  Radar,
  Rocket,
  FileText,
  CheckSquare,
  Building2,
  Settings,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useState } from 'react';

const navItems = [
  {
    label: 'Dashboard',
    path: '/',
    icon: LayoutDashboard,
  },
  {
    label: 'Map',
    path: '/map',
    icon: Map,
  },
  {
    label: 'SCOUT',
    icon: Radar,
    children: [
      { label: 'Deploy', path: '/scout/deploy', icon: Rocket },
      { label: 'Reports', path: '/scout/reports', icon: FileText },
      { label: 'Review', path: '/scout/review', icon: CheckSquare },
    ],
  },
  {
    label: 'Properties',
    path: '/properties',
    icon: Building2,
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: Settings,
  },
];

export function NavSidebar() {
  const location = useLocation();
  const [scoutOpen, setScoutOpen] = useState(
    location.pathname.startsWith('/scout')
  );

  return (
    <div className="w-56 bg-white border-r border-gray-200 flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-red-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">C</span>
          </div>
          <div>
            <h1 className="font-semibold text-gray-900 text-sm leading-tight">CSOKi</h1>
            <p className="text-[10px] text-gray-400 leading-tight">Site Selection Platform</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          if (item.children) {
            // SCOUT with sub-nav
            const isActive = location.pathname.startsWith('/scout');
            return (
              <div key={item.label}>
                <button
                  onClick={() => setScoutOpen(!scoutOpen)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'text-red-700 bg-red-50 font-medium'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  <item.icon className="w-4 h-4 flex-shrink-0" />
                  <span className="flex-1 text-left">{item.label}</span>
                  {scoutOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
                  )}
                </button>
                {scoutOpen && (
                  <div className="ml-4 mt-0.5 space-y-0.5">
                    {item.children.map((child) => (
                      <NavLink
                        key={child.path}
                        to={child.path}
                        className={({ isActive }) =>
                          `flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                            isActive
                              ? 'text-red-700 bg-red-50 font-medium'
                              : 'text-gray-500 hover:text-gray-900 hover:bg-gray-50'
                          }`
                        }
                      >
                        <child.icon className="w-3.5 h-3.5 flex-shrink-0" />
                        <span>{child.label}</span>
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          }

          return (
            <NavLink
              key={item.path}
              to={item.path!}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'text-red-700 bg-red-50 font-medium'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`
              }
            >
              <item.icon className="w-4 h-4 flex-shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-gray-100">
        <p className="text-[10px] text-gray-400 text-center">
          Phase 3 &middot; Unified Platform
        </p>
      </div>
    </div>
  );
}
