import { useRegisteredModels } from '../services/useModels.ts';
import { Link } from 'react-router-dom';

export default function ModelsList() {
  const { data: models, isLoading, error } = useRegisteredModels();

  if (isLoading) return <div>Loading models…</div>;
  if (error) return <div className="text-red-600">Error fetching models</div>;

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">Resources</h2>
      <ul className="space-y-2">
        {models?.map(name => (
          <li key={name}>
            <Link
              to={`/models/${name}`}
              className="text-blue-600 hover:underline"
            >
              {name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
