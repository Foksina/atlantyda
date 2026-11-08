import { HttpErrorResponse } from '@angular/common/http';
import { TimeoutError } from 'rxjs';

import type { ProblemDetails, ProblemFieldError } from '../../models/problem';
import { isJsonObject } from '../../models/json';

export type ApiErrorKind =
  | 'network'
  | 'timeout'
  | 'bad-request'
  | 'unauthorized'
  | 'forbidden'
  | 'not-found'
  | 'conflict'
  | 'unprocessable'
  | 'server'
  | 'unexpected';

const FALLBACK_MESSAGE: Record<ApiErrorKind, string> = {
  network: 'Nie udało się połączyć z serwerem.',
  timeout: 'Serwer nie odpowiedział w oczekiwanym czasie.',
  'bad-request': 'Żądanie jest niepoprawne.',
  unauthorized: 'Brak dostępu.',
  forbidden: 'Brak uprawnień do tej operacji.',
  'not-found': 'Nie znaleziono żądanych danych.',
  conflict: 'Operacja jest sprzeczna z bieżącym stanem danych.',
  unprocessable: 'Dane nie spełniają wymagań.',
  server: 'Serwer nie mógł obsłużyć żądania.',
  unexpected: 'Otrzymano nieoczekiwaną odpowiedź serwera.',
};

export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    readonly status: number | null,
    readonly problem: ProblemDetails | null,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function unexpectedResponse(): ApiError {
  return new ApiError('unexpected', null, null, FALLBACK_MESSAGE.unexpected);
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  if (error instanceof TimeoutError) {
    return new ApiError('timeout', null, null, FALLBACK_MESSAGE.timeout);
  }
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0) {
      return new ApiError('network', 0, null, FALLBACK_MESSAGE.network);
    }
    const problem = readProblem(error.error);
    const kind = kindForStatus(error.status);
    return new ApiError(kind, error.status, problem, messageFor(kind, problem));
  }
  return unexpectedResponse();
}

export function readProblem(value: unknown): ProblemDetails | null {
  if (!isJsonObject(value)) {
    return null;
  }
  const title = value['title'];
  const status = value['status'];
  if (typeof title !== 'string' || !isInteger(status)) {
    return null;
  }
  const problem: ProblemDetails = { title, status };
  const type = optionalString(value['type']);
  const detail = optionalString(value['detail']);
  const instance = optionalString(value['instance']);
  if (type !== undefined) {
    problem.type = type;
  }
  if (detail !== undefined) {
    problem.detail = detail;
  }
  if (instance !== undefined) {
    problem.instance = instance;
  }
  if (Object.hasOwn(value, 'errors')) {
    const errors = readFieldErrors(value['errors']);
    if (errors !== undefined) {
      problem.errors = errors;
    }
  }
  return problem;
}

function kindForStatus(status: number): ApiErrorKind {
  switch (status) {
    case 400:
      return 'bad-request';
    case 401:
      return 'unauthorized';
    case 403:
      return 'forbidden';
    case 404:
      return 'not-found';
    case 409:
      return 'conflict';
    case 422:
      return 'unprocessable';
    default:
      return status >= 500 && status <= 599 ? 'server' : 'unexpected';
  }
}

function messageFor(kind: ApiErrorKind, problem: ProblemDetails | null): string {
  if (problem !== null && isSafeMessage(problem.detail)) {
    return problem.detail;
  }
  if (problem !== null && isSafeMessage(problem.title)) {
    return problem.title;
  }
  return FALLBACK_MESSAGE[kind];
}

function isSafeMessage(value: string | undefined): value is string {
  if (value === undefined) {
    return false;
  }
  const trimmed = value.trim();
  if (trimmed.length === 0 || trimmed.length > 500) {
    return false;
  }
  return !/traceback|stack trace|exception/i.test(trimmed);
}

function isInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function readFieldErrors(value: unknown): ProblemFieldError[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const errors: ProblemFieldError[] = [];
  for (const item of value) {
    if (!isJsonObject(item)) {
      continue;
    }
    const field = item['field'];
    const message = item['message'];
    if (typeof field === 'string' && typeof message === 'string') {
      errors.push({ field, message });
    }
  }
  return errors;
}
