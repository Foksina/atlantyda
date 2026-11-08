import { environment } from './environment';

describe('environment', () => {
  it('uses the local API during the development test build', () => {
    expect(environment.production).toBe(false);
    expect(environment.apiUrl).toBe('http://localhost:8000/api');
  });
});
