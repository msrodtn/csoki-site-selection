import { Outlet } from 'react-router-dom';
import { NavSidebar } from './NavSidebar';

export function AppShell() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-gray-50">
      <NavSidebar />
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
