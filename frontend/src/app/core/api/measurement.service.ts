import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import type { Measurement, MeasurementQuery } from '../../models/measurement';
import type { ResourceId } from '../../models/resource-id';
import { API_URL } from '../config/api-url';
import { encodeResourceId, joinApiUrl } from './api-path';
import { parseMeasurement, parseMeasurementList } from './parse-measurement';

@Injectable({ providedIn: 'root' })
export class MeasurementService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = inject(API_URL);

  list(query: MeasurementQuery = {}): Observable<Measurement[]> {
    return this.http
      .get<unknown>(this.endpoint('measurements'), { params: measurementParams(query) })
      .pipe(map((body) => parseMeasurementList(body)));
  }

  getById(id: ResourceId): Observable<Measurement> {
    return this.http
      .get<unknown>(this.endpoint(`measurements/${encodeResourceId(id)}`))
      .pipe(map((body) => parseMeasurement(body)));
  }

  private endpoint(path: string): string {
    return joinApiUrl(this.apiUrl, path);
  }
}

export function measurementParams(query: MeasurementQuery): HttpParams {
  let params = new HttpParams();
  if (query.series !== undefined) {
    params = params.set('series', query.series);
  }
  if (query.from !== undefined) {
    params = params.set('from', query.from);
  }
  if (query.to !== undefined) {
    params = params.set('to', query.to);
  }
  if (query.sort !== undefined) {
    params = params.set('sort', query.sort);
  }
  if (query.limit !== undefined) {
    params = params.set('limit', String(query.limit));
  }
  return params;
}
