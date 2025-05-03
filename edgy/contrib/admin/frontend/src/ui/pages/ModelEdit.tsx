import { useParams, useNavigate } from "react-router-dom"
import { useEffect, useState } from "react"

export default function ModelEdit() {
  const { model, id } = useParams()
  const [fields, setFields] = useState<any[]>([])
  const [formData, setFormData] = useState<Record<string, any>>({})
  const navigate = useNavigate()

  useEffect(() => {
    fetch(`/admin/models/${model}/${id}`)
      .then(res => res.json())
      .then(data => setFormData(data))

    fetch(`/admin/models/${model}/schema`)
      .then(res => res.json())
      .then(data => {
        setFields(data.fields.filter((f: any) => !f.primary_key))
      })
  }, [model, id])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    fetch(`/admin/models/${model}/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    }).then(() => navigate(`/models/${model}`))
  }

  return (
    <div>
      <h2 className="text-xl font-bold mb-4 capitalize">Edit {model}</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        {fields.map(field => (
          <div key={field.name}>
            <label className="block mb-1 font-medium">{field.name}</label>
            <input
              name={field.name}
              value={formData[field.name]}
              onChange={handleChange}
              className="border px-3 py-2 w-full"
            />
          </div>
        ))}
        <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded">Update</button>
      </form>
    </div>
  )
}
