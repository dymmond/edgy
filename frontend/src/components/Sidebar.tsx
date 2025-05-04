import { NavLink } from 'react-router-dom';
import { Home, Database, Settings } from 'lucide-react';

const navItems = [
  { name: 'Dashboard', path: '/dashboard', icon: <Home size={20} /> },
  { name: 'Models',    path: '/models',    icon: <Database size={20} /> },
  { name: 'Settings',  path: '/settings',  icon: <Settings size={20} /> },
];

export default function Sidebar() {
  return (
    <aside className="w-64 bg-gray-800 text-gray-100 flex flex-col">
      <div className="py-4 px-6 font-bold text-lg border-b border-gray-700">
        Edgy Admin
      </div>
      <nav className="flex-1 px-4 py-6 space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center px-3 py-2 rounded hover:bg-gray-700 ${
                isActive ? 'bg-gray-700' : ''
              }`
            }
          >
            {item.icon}
            <span className="ml-3">{item.name}</span>
          </NavLink>
        ))}
      </nav>
      <div className="p-4 border-t border-gray-700 text-sm">
        © 2025 Edgy Inc.
      </div>
    </aside>)
}
