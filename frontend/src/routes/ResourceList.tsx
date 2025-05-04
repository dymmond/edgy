import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  useModelSchema,
  useResourceList,
  useDeleteResource,
} from '../services/useModels.ts';
import { Table } from '../components/Table.tsx';

export default function ResourceList() {
  const { name } = useParams<{ name: string }>();
  const [page, setPage] = useState(1);
  const perPage = 25;
  const resourceName = name || '';

  const { data: schema, isLoading: loadingSchema } = useModelSchema(resourceName);
  const {
    data: resources,
    isLoading: loadingResources,
    error,
  } = useResourceList(resourceName, page, perPage);
  const deleteMutation = useDeleteResource(resourceName);

  if (loadingSchema || loadingResources) return <div>Loading…</div>;
  if (error) return <div className="text-red-600">Error loading resources</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-semibold capitalize">
          {resourceName}
        </h2>
        <Link
          to={`/models/${resourceName}/create`}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Create
        </Link>
      </div>

      <Table
        columns={
          schema.fields.map((f: any) => ({ header: f.name, accessorKey: f.name }))
        }
        data={resources!.items}
        onDelete={id => deleteMutation.mutate(id)}
      />

      {/* Simple Pagination */}
      <div className="mt-4 flex justify-between">
        <button
          onClick={() => setPage(p => Math.max(p - 1, 1))}
          disabled={page === 1}
          className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
        >
          Previous
        </button>
        <span>
          Page {page} of {Math.ceil((resources!.total || 0) / perPage)}
        </span>
        <button
          onClick={() => setPage(p => p + 1)}
          disabled={page * perPage >= (resources!.total || 0)}
          className="px-3 py-1 bg-gray-200 rounded disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
