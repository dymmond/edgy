// File: src/ui/Layout.tsx
import { Outlet, Link, useLocation } from "react-router-dom"
import { useEffect, useState } from "react"
import { Home, Database, Settings } from "lucide-react"

const navLinks = [
  { name: "Dashboard", icon: <Home size={18} />, path: "/" },
  { name: "Models", icon: <Database size={18} />, path: "/models" },
  { name: "Settings", icon: <Settings size={18} />, path: "/settings" },
]

export default function Layout() {
  const { pathname } = useLocation()
  const [models, setModels] = useState<string[]>([])

  useEffect(() => {
    fetch("/admin/models")
      .then(res => res.json())
      .then(data => setModels(data.models))
  }, [])

  return (
    <div className="flex min-h-screen bg-gray-100">
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-5 text-2xl font-bold tracking-wide border-b border-gray-700">⚙️ Edgy Admin</div>
        <nav className="flex-1 p-4 space-y-2">
          {navLinks.map(link => (
            <Link
              key={link.path}
              to={link.path}
              className={`flex items-center gap-2 px-4 py-2 rounded hover:bg-gray-700 ${pathname === link.path ? "bg-gray-800" : ""}`}
            >
              {link.icon}
              {link.name}
            </Link>
          ))}
          <hr className="my-4 border-gray-700" />
          <div className="text-sm text-gray-400 px-4 mb-2">Registered Models</div>
          {models.map(model => (
            <Link
              key={model}
              to={`/models/${model}`}
              className={`block px-4 py-2 rounded hover:bg-gray-700 capitalize ${pathname.includes(`/models/${model}`) ? "bg-gray-800" : ""}`}
            >
              {model}
            </Link>
          ))}
        </nav>
      </aside>

      <main className="flex-1">
        <header className="bg-white border-b shadow-sm px-6 py-4 flex justify-between items-center">
          <h1 className="text-xl font-semibold">Edgy Admin</h1>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">admin@example.com</span>
            <div className="w-8 h-8 bg-gray-300 rounded-full" />
          </div>
        </header>

        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
