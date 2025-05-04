import { Menu, Sun, Moon } from 'lucide-react';

export default function Navbar() {
  return (
    <header className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-200">
      <button className="p-2 rounded hover:bg-gray-100">
        <Menu size={24} />
      </button>
      <div className="flex items-center space-x-4">
        <button className="p-2 rounded hover:bg-gray-100">
          <Sun  size={20} />
        </button>
        <button className="p-2 rounded hover:bg-gray-100">
          <Moon size={20} />
        </button>
        <div className="text-sm font-medium">Admin User</div>
      </div>
    </header>
  );
}
