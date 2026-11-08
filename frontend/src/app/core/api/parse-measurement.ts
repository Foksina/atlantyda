import type { Measurement } from '../../models/measurement';
import { isJsonObject } from '../../models/json';
import { isResourceId } from '../../models/resource-id';
import { unexpectedResponse } from './api-error';

const ISO_DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

export function parseMeasurementList(value: unknown): Measurement[] {
  if (!Array.isArray(value)) {
    throw unexpectedResponse();
  }
  return value.map((item) => parseMeasurement(item));
}

export function parseMeasurement(value: unknown): Measurement {
  if (!isJsonObject(value) || !isResourceId(value['id']) || !isResourceId(value['seriesId'])) {
    throw unexpectedResponse();
  }
  if (!isFiniteNumber(value['value']) || !isIsoDateTime(value['timestamp'])) {
    throw unexpectedResponse();
  }
  const measurement: Measurement = {
    id: value['id'],
    seriesId: value['seriesId'],
    value: value['value'],
    timestamp: value['timestamp'],
  };
  if (Object.hasOwn(value, 'sensorId')) {
    if (!isResourceId(value['sensorId'])) {
      throw unexpectedResponse();
    }
    measurement.sensorId = value['sensorId'];
  }
  return measurement;
}

function isIsoDateTime(value: unknown): value is string {
  return typeof value === 'string' && ISO_DATE_TIME.test(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
