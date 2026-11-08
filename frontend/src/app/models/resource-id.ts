export type ResourceId = number | string;

export function isResourceId(value: unknown): value is ResourceId {
  if (typeof value === 'string') {
    return true;
  }
  return typeof value === 'number' && Number.isInteger(value);
}
