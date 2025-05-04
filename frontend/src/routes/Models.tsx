import React, { useState } from 'react';
import { useModelSchema, useResourceList, useDeleteResource } from '../services/useModels';
import { Table } from '../components/Table';

export default function Models() {
  const [page, setPage] = useState(1);
  const perPage = 25;
  const resourceName = 'your_model_name'; // e.g. fetched from route params
  const { data: schema } = useModelSchema(resourceName);
  const { data, isLoading, error } = useResourceList(resourceName, page, perPage);
  const deleteMutation = useDeleteResource(resourceName);

  if (isLoading) return <div>Loading…</div>;
  if (error) return <div className="text-red-600">Error loading resources</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-semibold">Models: {resourceName}</h2>
        {/* TODO: Add “Create” button here */}
      </div>
      <Table
        columns={schema.fields.map((f: any) => ({ Header: f.name, accessor: f.name }))}
        data={data.items}
        onDelete={(id) => deleteMutation.mutate(id)}
      />
      {/* TODO: Pagination controls below */}
    </div>
  );
}
