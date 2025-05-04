import { Routes, Route, Navigate } from 'react-router-dom';
import AdminLayout from './layouts/AdminLayout';
import Dashboard   from './routes/Dashboard';
import Models      from './routes/Models';
import NotFound    from './routes/NotFound';

export default function App() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/models"    element={<Models />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
