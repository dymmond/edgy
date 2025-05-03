import React from "react"
import ReactDOM from "react-dom/client"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import Layout from "./ui/pages/Layout.tsx"
import Dashboard from "./ui/pages/Dashboard"
import Models from "./ui/pages/Models"
import ModelList from "./ui/pages/ModelList"
import ModelCreate from "./ui/pages/ModelCreate"
import ModelEdit from "./ui/pages/ModelEdit"
import "./index.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="models" element={<Models />} />
          <Route path="models/:model" element={<ModelList />} />
          <Route path="models/:model/create" element={<ModelCreate />} />
          <Route path="models/:model/:id/edit" element={<ModelEdit />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
