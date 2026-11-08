import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { TestBed } from '@angular/core/testing';

import { routes } from './app.routes';

describe('application routes', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter(routes)],
    });
  });

  it('shows the shell and the temporary measurements view', async () => {
    const harness = await RouterTestingHarness.create('/pomiary');
    const page = harness.fixture.nativeElement as HTMLElement;

    expect(page.querySelector('h1')?.textContent).toContain('Pomiary');
    expect(page.textContent).toContain('Publiczny podgląd pomiarów nie jest jeszcze gotowy.');
    expect(page.textContent).toContain('Niezalogowano');
    expect(page.querySelector('footer')?.textContent).toContain('Atlantyda');
    const current = page.querySelector('.nav__link.is-active');
    expect(current?.textContent).toContain('Pomiary');
    expect(current?.getAttribute('aria-current')).toBe('page');
  });

  it('opens series and administration as temporary views', async () => {
    const harness = await RouterTestingHarness.create();

    await harness.navigateByUrl('/serie');
    expect(pageHeading(harness)).toContain('Serie pomiarowe');
    expect(pageText(harness)).toContain('nie są jeszcze pokazane');

    await harness.navigateByUrl('/admin');
    expect(pageHeading(harness)).toContain('Panel administratora');
    expect(pageText(harness)).toContain('nie jest jeszcze dostępny');
  });

  it('redirects the root and unknown paths to measurements', async () => {
    const harness = await RouterTestingHarness.create();
    const router = TestBed.inject(Router);

    await harness.navigateByUrl('/');
    expect(router.url).toBe('/pomiary');

    await harness.navigateByUrl('/nie-ma-takiej-trasy');
    expect(router.url).toBe('/pomiary');
    expect(pageHeading(harness)).toContain('Pomiary');
  });
});

function pageHeading(harness: RouterTestingHarness): string {
  return (harness.fixture.nativeElement as HTMLElement).querySelector('h1')?.textContent ?? '';
}

function pageText(harness: RouterTestingHarness): string {
  return (harness.fixture.nativeElement as HTMLElement).textContent ?? '';
}
