import type { ResourceId } from '../../models/resource-id';

export function joinApiUrl(base: string, path: string): string {
  const normalizedBase = base.replace(/\/+$/, '');
  const normalizedPath = path.replace(/^\/+/, '');
  return `${normalizedBase}/${normalizedPath}`;
}

export function encodeResourceId(id: ResourceId): string {
  return encodeURIComponent(String(id));
}
