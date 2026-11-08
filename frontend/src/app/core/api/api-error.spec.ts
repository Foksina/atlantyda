import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { TimeoutError } from 'rxjs';

import { API_TIMEOUT_MS } from '../config/api-url';
import { apiErrorInterceptor } from './api-error.interceptor';
import { ApiError, toApiError } from './api-error';

describe('API errors', () => {
  let httpClient: HttpClient;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
        { provide: API_TIMEOUT_MS, useValue: 120_000 },
      ],
    });
    httpClient = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('maps problem details for 400, 401, 403, 404, 409 and 422', () => {
    const cases = [
      { status: 400, kind: 'bad-request', detail: 'Parametry zapytania są niepoprawne.' },
      { status: 401, kind: 'unauthorized', detail: 'Wymagany jest token administratora.' },
      { status: 403, kind: 'forbidden', detail: 'Podane bieżące hasło jest niepoprawne.' },
      { status: 404, kind: 'not-found', detail: 'Seria pomiarowa nie istnieje.' },
      { status: 409, kind: 'conflict', detail: 'Nowy zakres nie obejmuje istniejących pomiarów.' },
      {
        status: 422,
        kind: 'unprocessable',
        detail: 'Wartość jest poza dopuszczalnym przedziałem serii.',
      },
    ] as const;

    for (const item of cases) {
      const errors: ApiError[] = [];
      httpClient.get('/api/series').subscribe({
        error: (error: unknown) => errors.push(error as ApiError),
      });
      http.expectOne('/api/series').flush(
        {
          type: 'about:blank',
          title: 'Błąd',
          status: item.status,
          detail: item.detail,
          instance: '/api/series',
          errors: [{ field: 'sort', message: 'Dozwolone wartości to timestamp i -timestamp.' }],
        },
        { status: item.status, statusText: 'Error' },
      );

      expect(errors).toHaveLength(1);
      expect(errors[0]?.kind).toBe(item.kind);
      expect(errors[0]?.status).toBe(item.status);
      expect(errors[0]?.message).toBe(item.detail);
      expect(errors[0]?.message).not.toContain('Http failure');
      expect(errors[0]?.problem?.errors?.[0]).toEqual({
        field: 'sort',
        message: 'Dozwolone wartości to timestamp i -timestamp.',
      });
    }
  });

  it('maps a server error without exposing a non-problem body', () => {
    const errors: ApiError[] = [];
    httpClient.get('/api/series').subscribe({
      error: (error: unknown) => errors.push(error as ApiError),
    });
    http
      .expectOne('/api/series')
      .flush(
        { error: 'Traceback (most recent call last): secret' },
        { status: 500, statusText: 'Server Error' },
      );

    expect(errors[0]?.kind).toBe('server');
    expect(errors[0]?.problem).toBeNull();
    expect(errors[0]?.message).toBe('Serwer nie mógł obsłużyć żądania.');
    expect(errors[0]?.message).not.toContain('Traceback');
    expect(errors[0]?.message).not.toContain('secret');
  });

  it('uses the problem title when the detail looks like a stack trace', () => {
    const errors: ApiError[] = [];
    httpClient.get('/api/series/9').subscribe({
      error: (error: unknown) => errors.push(error as ApiError),
    });
    http.expectOne('/api/series/9').flush(
      {
        title: 'Nie znaleziono',
        status: 404,
        detail: 'Traceback (most recent call last): File "views.py"',
      },
      { status: 404, statusText: 'Not Found' },
    );

    expect(errors[0]?.message).toBe('Nie znaleziono');
  });

  it('maps a dropped connection to a network error', () => {
    const errors: ApiError[] = [];
    httpClient.get('/api/measurements').subscribe({
      error: (error: unknown) => errors.push(error as ApiError),
    });
    http.expectOne('/api/measurements').error(new ProgressEvent('error'));

    expect(errors[0]?.kind).toBe('network');
    expect(errors[0]?.status).toBe(0);
    expect(errors[0]?.message).toBe('Nie udało się połączyć z serwerem.');
  });

  it('maps a TimeoutError value directly', () => {
    const error = toApiError(new TimeoutError());
    expect(error.kind).toBe('timeout');
    expect(error.problem).toBeNull();
  });
});

describe('API timeout', () => {
  it('maps an HTTP timeout without the request address', async () => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
        { provide: API_TIMEOUT_MS, useValue: 15 },
      ],
    });
    const client = TestBed.inject(HttpClient);
    const http = TestBed.inject(HttpTestingController);
    const errors: ApiError[] = [];
    client.get('/slow').subscribe({
      error: (error: unknown) => errors.push(error as ApiError),
    });
    http.expectOne('/slow');

    await new Promise((resolve) => setTimeout(resolve, 40));

    expect(errors[0]?.kind).toBe('timeout');
    expect(errors[0]?.message).toBe('Serwer nie odpowiedział w oczekiwanym czasie.');
    expect(errors[0]?.message).not.toContain('/slow');
    http.verify();
  });
});
