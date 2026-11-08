import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { API_URL } from '../config/api-url';
import { ApiError } from './api-error';
import { SeriesService } from './series.service';

const apiUrl = 'http://api.test/api';

describe('SeriesService', () => {
  let service: SeriesService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_URL, useValue: apiUrl },
      ],
    });
    service = TestBed.inject(SeriesService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('does not send a request until subscription', () => {
    service.list();
    http.expectNone(`${apiUrl}/series`);
  });

  it('requests the series collection and maps the response', () => {
    const received: unknown[] = [];
    service.list().subscribe((series) => received.push(series));

    const request = http.expectOne(`${apiUrl}/series`);
    expect(request.request.method).toBe('GET');
    expect(request.request.params.keys()).toEqual([]);
    request.flush([
      {
        id: 4,
        name: 'Temperatura wody',
        minValue: 4,
        maxValue: 28,
        color: '#1f77b4',
        icon: 'thermometer',
        unit: '°C',
      },
    ]);

    expect(received).toEqual([
      [
        {
          id: 4,
          name: 'Temperatura wody',
          minValue: 4,
          maxValue: 28,
          color: '#1f77b4',
          icon: 'thermometer',
          unit: '°C',
        },
      ],
    ]);
  });

  it('maps an empty series list', () => {
    const received: unknown[] = [];
    service.list().subscribe((series) => received.push(series));

    http.expectOne(`${apiUrl}/series`).flush([]);

    expect(received).toEqual([[]]);
  });

  it('keeps optional icon and unit absent when the payload omits them', () => {
    const received: unknown[] = [];
    service.getById(4).subscribe((series) => received.push(series));

    const request = http.expectOne(`${apiUrl}/series/4`);
    expect(request.request.method).toBe('GET');
    request.flush({
      id: 'series-4',
      name: 'Temperatura wody',
      minValue: 4.5,
      maxValue: 28,
      color: '#1f77b4',
    });

    expect(received).toEqual([
      {
        id: 'series-4',
        name: 'Temperatura wody',
        minValue: 4.5,
        maxValue: 28,
        color: '#1f77b4',
      },
    ]);
  });

  it('encodes the series id and accepts a null icon', () => {
    service.getById('a/b').subscribe();

    const request = http.expectOne(`${apiUrl}/series/a%2Fb`);
    request.flush({
      id: 'a/b',
      name: 'Seria',
      minValue: 0,
      maxValue: 1,
      color: '#000000',
      icon: null,
      unit: null,
    });
  });

  it('rejects a response that is not a series list', () => {
    const errors: unknown[] = [];
    service.list().subscribe({
      error: (error: unknown) => errors.push(error),
    });

    http.expectOne(`${apiUrl}/series`).flush({ items: [] });

    expect(errors).toHaveLength(1);
    expect(errors[0]).toBeInstanceOf(ApiError);
    expect((errors[0] as ApiError).kind).toBe('unexpected');
    expect((errors[0] as ApiError).message).toBe('Otrzymano nieoczekiwaną odpowiedź serwera.');
  });
});
