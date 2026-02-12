import { NavLink, useLocation, useNavigate } from 'react-router-dom';
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
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useState, useCallback, useEffect, useRef } from 'react';

const MIN_WIDTH = 64;
const MAX_WIDTH = 320;
const DEFAULT_WIDTH = 224;
const COLLAPSE_SNAP = 80;
const STORAGE_KEY = 'csoki-sidebar-width';
const COLLAPSED_KEY = 'csoki-sidebar-collapsed';

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

function loadSidebarState() {
  try {
    const collapsed = localStorage.getItem(COLLAPSED_KEY) === 'true';
    const width = parseInt(localStorage.getItem(STORAGE_KEY) || String(DEFAULT_WIDTH), 10);
    return { collapsed, width: collapsed ? MIN_WIDTH : Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, width)) };
  } catch {
    return { collapsed: false, width: DEFAULT_WIDTH };
  }
}

export function NavSidebar({ onWidthChange }: { onWidthChange?: (width: number) => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [scoutOpen, setScoutOpen] = useState(
    location.pathname.startsWith('/scout')
  );

  const initial = loadSidebarState();
  const [collapsed, setCollapsed] = useState(initial.collapsed);
  const [width, setWidth] = useState(initial.width);
  const [isDragging, setIsDragging] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const actualWidth = collapsed ? MIN_WIDTH : width;

  // Persist state
  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSED_KEY, String(collapsed));
      if (!collapsed) localStorage.setItem(STORAGE_KEY, String(width));
    } catch { /* ignore */ }
  }, [collapsed, width]);

  // Notify parent of width changes
  useEffect(() => {
    onWidthChange?.(actualWidth);
  }, [actualWidth, onWidthChange]);

  // Close SCOUT submenu when collapsed
  useEffect(() => {
    if (collapsed) setScoutOpen(false);
  }, [collapsed]);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  // Drag resize
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = e.clientX;
      if (newWidth < COLLAPSE_SNAP) {
        setCollapsed(true);
        setIsDragging(false);
      } else {
        setCollapsed(false);
        setWidth(Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newWidth)));
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging]);

  return (
    <div
      ref={sidebarRef}
      className="relative bg-white border-r border-gray-200 flex flex-col h-full flex-shrink-0"
      style={{
        width: actualWidth,
        transition: isDragging ? 'none' : 'width 200ms ease',
      }}
    >
      {/* Logo */}
      <div className="px-3 py-5 border-b border-gray-100">
        <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-2.5 px-2'}`}>
          <div className="w-8 h-8 rounded-lg bg-red-600 flex items-center justify-center flex-shrink-0">
            <span className="text-white font-bold text-sm">C</span>
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <h1 className="font-semibold text-gray-900 text-sm leading-tight whitespace-nowrap">CSOKi</h1>
              <p className="text-[10px] text-gray-400 leading-tight whitespace-nowrap">Site Selection Platform</p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto overflow-x-hidden">
        {navItems.map((item) => {
          if (item.children) {
            const isActive = location.pathname.startsWith('/scout');

            if (collapsed) {
              // Collapsed: just show icon, link to first child
              return (
                <NavLink
                  key={item.label}
                  to="/scout/deploy"
                  title={item.label}
                  className={`flex items-center justify-center p-2 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'text-red-700 bg-red-50 font-medium'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  <item.icon className="w-4 h-4" />
                </NavLink>
              );
            }

            return (
              <div key={item.label}>
                <button
                  onClick={() => {
                    if (!scoutOpen) {
                      setScoutOpen(true);
                      navigate('/scout/deploy');
                    } else {
                      setScoutOpen(false);
                    }
                  }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'text-red-700 bg-red-50 font-medium'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  <item.icon className="w-4 h-4 flex-shrink-0" />
                  <span className="flex-1 text-left whitespace-nowrap overflow-hidden">{item.label}</span>
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
                        <span className="whitespace-nowrap overflow-hidden">{child.label}</span>
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          }

          if (collapsed) {
            return (
              <NavLink
                key={item.path}
                to={item.path!}
                end={item.path === '/'}
                title={item.label}
                className={({ isActive }) =>
                  `flex items-center justify-center p-2 rounded-lg text-sm transition-colors ${
                    isActive
                      ? 'text-red-700 bg-red-50 font-medium'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <item.icon className="w-4 h-4" />
              </NavLink>
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
              <span className="whitespace-nowrap overflow-hidden">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer with collapse toggle */}
      <div className="px-2 py-3 border-t border-gray-100">
        <button
          onClick={toggleCollapse}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={`w-full flex items-center ${collapsed ? 'justify-center' : 'gap-2 px-3'} py-2 rounded-lg text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors`}
        >
          {collapsed ? (
            <PanelLeftOpen className="w-4 h-4" />
          ) : (
            <>
              <PanelLeftClose className="w-4 h-4 flex-shrink-0" />
              <span className="whitespace-nowrap">Collapse</span>
            </>
          )}
        </button>
      </div>

      {/* Drag handle */}
      <div
        onMouseDown={handleMouseDown}
        className="absolute top-0 right-0 w-1 h-full cursor-col-resize hover:bg-red-500/20 active:bg-red-500/30 transition-colors z-10"
      />
    </div>
  );
}
