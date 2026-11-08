import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import type { Series } from '../../models/series';
import type { ResourceId } from '../../models/resource-id';
import { API_URL } from '../config/api-url';
import { encodeResourceId, joinApiUrl } from './api-path';
import { parseSeries, parseSeriesList } from './parse-series';

@Injectable({ providedIn: 'root' })
export class SeriesService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = inject(API_URL);

  list(): Observable<Series[]> {
    return this.http
      .get<unknown>(this.endpoint('series'))
      .pipe(map((body) => parseSeriesList(body)));
  }

  getById(id: ResourceId): Observable<Series> {
    return this.http
      .get<unknown>(this.endpoint(`series/${encodeResourceId(id)}`))
      .pipe(map((body) => parseSeries(body)));
  }

  private endpoint(path: string): string {
    return joinApiUrl(this.apiUrl, path);
  }
}
