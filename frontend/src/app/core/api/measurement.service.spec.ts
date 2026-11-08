import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { API_URL } from '../config/api-url';
import { ApiError } from './api-error';
import { MeasurementService } from './measurement.service';

const apiUrl = 'http://api.test/api';

describe('MeasurementService', () => {
  let service: MeasurementService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_URL, useValue: apiUrl },
      ],
    });
    service = TestBed.inject(MeasurementService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('does not send a request until subscription', () => {
    service.list();
    http.expectNone(`${apiUrl}/measurements`);
  });

  it('sends only the filter parameters present in the query', () => {
    service
      .list({
        series: '1,3',
        from: '2026-11-01T00:00:00Z',
        to: '2026-11-02T00:00:00Z',
        sort: '-timestamp',
        limit: 2,
      })
      .subscribe();

    const request = http.expectOne((candidate) => candidate.url === `${apiUrl}/measurements`);
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('series')).toBe('1,3');
    expect(request.request.params.get('from')).toBe('2026-11-01T00:00:00Z');
    expect(request.request.params.get('to')).toBe('2026-11-02T00:00:00Z');
    expect(request.request.params.get('sort')).toBe('-timestamp');
    expect(request.request.params.get('limit')).toBe('2');
    request.flush([]);
  });

  it('does not add default sort or limit when the query is empty', () => {
    service.list().subscribe();

    const request = http.expectOne((candidate) => candidate.url === `${apiUrl}/measurements`);
    expect(request.request.params.keys()).toEqual([]);
    request.flush([]);
  });

  it('keeps reserved characters inside a single series parameter', () => {
    service.list({ series: '1&limit=999' }).subscribe();

    const request = http.expectOne((candidate) => candidate.url === `${apiUrl}/measurements`);
    expect(request.request.params.get('series')).toBe('1&limit=999');
    expect(request.request.params.get('limit')).toBeNull();
    request.flush([]);
  });

  it('maps measurements and an empty list', () => {
    const received: unknown[] = [];
    service.list({ limit: 2 }).subscribe((measurements) => received.push(measurements));

    http
      .expectOne((candidate) => candidate.url === `${apiUrl}/measurements`)
      .flush([
        {
          id: 7,
          seriesId: 4,
          sensorId: 4,
          value: 12.5,
          timestamp: '2026-11-01T12:49:16Z',
        },
      ]);

    expect(received).toEqual([
      [
        {
          id: 7,
          seriesId: 4,
          sensorId: 4,
          value: 12.5,
          timestamp: '2026-11-01T12:49:16Z',
        },
      ],
    ]);

    service.list({ series: '999999999' }).subscribe((measurements) => received.push(measurements));
    http.expectOne((candidate) => candidate.url === `${apiUrl}/measurements`).flush([]);
    expect(received[1]).toEqual([]);
  });

  it('maps a measurement without sensorId and encodes the id', () => {
    const received: unknown[] = [];
    service.getById('m/1').subscribe((measurement) => received.push(measurement));

    const request = http.expectOne(`${apiUrl}/measurements/m%2F1`);
    expect(request.request.method).toBe('GET');
    request.flush({
      id: 'm/1',
      seriesId: 4,
      value: 1,
      timestamp: '2026-11-01T12:49:16.500+02:00',
    });

    expect(received).toEqual([
      {
        id: 'm/1',
        seriesId: 4,
        value: 1,
        timestamp: '2026-11-01T12:49:16.500+02:00',
      },
    ]);
  });

  it('rejects a measurement with an invalid timestamp', () => {
    const errors: unknown[] = [];
    service.getById(7).subscribe({
      error: (error: unknown) => errors.push(error),
    });

    http.expectOne(`${apiUrl}/measurements/7`).flush({
      id: 7,
      seriesId: 4,
      value: 12,
      timestamp: 'wczoraj',
    });

    expect(errors[0]).toBeInstanceOf(ApiError);
    expect((errors[0] as ApiError).kind).toBe('unexpected');
    expect((errors[0] as ApiError).message).not.toContain('wczoraj');
  });
});
