import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { map } from 'rxjs';

@Component({
  selector: 'app-tymczasowy',
  templateUrl: './tymczasowy.html',
  styleUrl: './tymczasowy.scss',
})
export class TymczasowyView {
  private readonly data = toSignal(
    inject(ActivatedRoute).data.pipe(map((value) => routeData(value))),
    { initialValue: {} },
  );

  protected heading(): string {
    return text(this.data(), 'heading');
  }

  protected summary(): string {
    return text(this.data(), 'summary');
  }
}

function routeData(value: object): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    data[key] = item;
  }
  return data;
}

function text(data: Record<string, unknown>, key: string): string {
  const value = data[key];
  return typeof value === 'string' ? value : '';
}
