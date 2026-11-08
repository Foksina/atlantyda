import type { Series } from '../../models/series';
import { isJsonObject } from '../../models/json';
import { isResourceId } from '../../models/resource-id';
import { unexpectedResponse } from './api-error';

export function parseSeriesList(value: unknown): Series[] {
  if (!Array.isArray(value)) {
    throw unexpectedResponse();
  }
  return value.map((item) => parseSeries(item));
}

export function parseSeries(value: unknown): Series {
  if (!isJsonObject(value) || !isResourceId(value['id']) || !isFiniteNumber(value['minValue'])) {
    throw unexpectedResponse();
  }
  if (!isFiniteNumber(value['maxValue']) || typeof value['name'] !== 'string') {
    throw unexpectedResponse();
  }
  if (typeof value['color'] !== 'string') {
    throw unexpectedResponse();
  }
  const series: Series = {
    id: value['id'],
    name: value['name'],
    minValue: value['minValue'],
    maxValue: value['maxValue'],
    color: value['color'],
  };
  if (Object.hasOwn(value, 'icon')) {
    series.icon = readNullableString(value['icon']);
  }
  if (Object.hasOwn(value, 'unit')) {
    series.unit = readNullableString(value['unit']);
  }
  return series;
}

function readNullableString(value: unknown): string | null {
  if (value === null || typeof value === 'string') {
    return value;
  }
  throw unexpectedResponse();
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
