import { useParams, Link } from "react-router-dom"
import { useEffect, useState } from "react"

export default function ModelList() {
  const { model } = useParams()
  const [items, setItems] = useState<any[]>([])

  useEffect(() => {
    fetch(`/admin/models/${model}`)
      .then(res => res.json())
      .then(data => setItems(data))
  }, [model])

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold capitalize">{model}</h2>
        <Link to={`/models/${model}/create`} className="bg-blue-600 text-white px-4 py-2 rounded">Create New</Link>
      </div>
      <table className="w-full bg-white border">
        <thead>
          <tr>
            {items[0] && Object.keys(items[0]).map(key => (
              <th key={key} className="border px-2 py-1 text-left">{key}</th>
            ))}
            <th className="border px-2 py-1">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={index}>
              {Object.values(item).map((val, i) => (
                <td key={i} className="border px-2 py-1">{String(val)}</td>
              ))}
              <td className="border px-2 py-1">
                <Link to={`/models/${model}/${item.id}/edit`} className="text-blue-600">Edit</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
