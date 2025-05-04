import { Routes, Route, Navigate } from 'react-router-dom';
import AdminLayout from './layouts/AdminLayout';
import Dashboard   from './routes/Dashboard';
import ModelsList  from './routes/ModelsList';
import ResourceList from './routes/ResourceList';
import NotFound    from './routes/NotFound';

export default function App() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/models" element={<ModelsList />} />
        <Route path="/models/:name" element={<ResourceList />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
