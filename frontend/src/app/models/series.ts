import type { ResourceId } from './resource-id';

export interface Series {
  id: ResourceId;
  name: string;
  minValue: number;
  maxValue: number;
  color: string;
  icon?: string | null;
  unit?: string | null;
}
