import {
  useReactTable,
  getCoreRowModel,
  ColumnDef,
  flexRender,
} from '@tanstack/react-table';
import { Trash2 } from 'lucide-react';

interface TableProps<T> {
  columns: ColumnDef<T, any>[];
  data: T[];
  onDelete: (id: string | number) => void;
}

export function Table<T>({ columns, data, onDelete }: TableProps<T>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),      // ← fixed here
  });

  return (
    <div className="overflow-x-auto bg-white rounded shadow">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
        {table.getHeaderGroups().map(hg => (
          <tr key={hg.id}>
            {hg.headers.map(header => (
              <th
                key={header.id}
                className="px-4 py-2 text-left text-sm font-medium text-gray-500"
              >
                {flexRender(
                  header.column.columnDef.header,
                  header.getContext()
                )}
              </th>
            ))}
            <th className="px-4 py-2" />
          </tr>
        ))}
        </thead>
        <tbody className="divide-y divide-gray-100">
        {table.getRowModel().rows.map(row => (
          <tr key={row.id}>
            {row.getVisibleCells().map(cell => (
              <td
                key={cell.id}
                className="px-4 py-2 text-sm text-gray-700"
              >
                {flexRender(
                  cell.column.columnDef.cell,
                  cell.getContext()
                )}
              </td>
            ))}
            <td className="px-4 py-2 text-right">
              <button onClick={() => onDelete((row.original as any).id)}>
                <Trash2
                  size={16}
                  className="text-red-500 hover:text-red-700"
                />
              </button>
            </td>
          </tr>
        ))}
        </tbody>
      </table>
    </div>
  );
}
