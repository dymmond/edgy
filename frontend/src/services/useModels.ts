import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listModels,
  getSchema,
  listResources,
  deleteResource,
} from './api';

export function useRegisteredModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: () => listModels(),
  });
}

export function useModelSchema(name: string) {
  return useQuery({
    queryKey: ['schema', name],
    queryFn: () => getSchema(name),
    enabled: Boolean(name),
  });
}

export function useResourceList(name: string, page: number, perPage: number) {
  return useQuery({
    queryKey: ['resources', name, page, perPage],
    queryFn: () => listResources(name, page, perPage),
    keepPreviousData: true,
  });
}

export function useDeleteResource(name: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string | number) => deleteResource(name, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resources', name] });
    },
  });
}
