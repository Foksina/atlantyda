import type { ResourceId } from './resource-id';

/** Znacznik czasu ISO 8601 ze strefą, np. 2026-11-08T12:00:00Z. */
export type IsoDateTime = string;

export type MeasurementSort = 'timestamp' | '-timestamp';

/** Parametry zapytania GET /api/measurements. Pominięte pola nie są wysyłane. */
export interface MeasurementQuery {
  series?: string;
  from?: IsoDateTime;
  to?: IsoDateTime;
  sort?: MeasurementSort;
  limit?: number;
}

export interface Measurement {
  id: ResourceId;
  seriesId: ResourceId;
  sensorId?: ResourceId;
  value: number;
  timestamp: IsoDateTime;
}
