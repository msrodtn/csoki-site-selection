import { Outlet, NavLink } from 'react-router-dom';
import { Rocket, FileText, CheckSquare } from 'lucide-react';

const subNavItems = [
  { label: 'Deploy', path: '/scout/deploy', icon: Rocket },
  { label: 'Reports', path: '/scout/reports', icon: FileText },
  { label: 'Review', path: '/scout/review', icon: CheckSquare },
];

export function ScoutLayout() {
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Sub-navigation */}
      <div className="bg-white border-b border-gray-200 px-6">
        <div className="max-w-6xl mx-auto flex items-center gap-6">
          {subNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-2 py-3 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? 'border-red-600 text-red-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <Outlet />
      </div>
    </div>
  );
}
