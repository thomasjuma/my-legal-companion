import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { httpErrorMessage } from '../core/http-error-message';
import { CaseReferenceService } from '../services/case-reference.service';
import { HealthService } from '../services/health.service';
import { CaseReference } from '../models/api.models';

@Component({
  selector: 'app-home',
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './home.html',
  styleUrl: './home.css',
})
export class HomeComponent implements OnInit {
  private readonly health = inject(HealthService);
  private readonly caseRefApi = inject(CaseReferenceService);

  protected readonly apiStatus = signal<string | null>(null);

  protected readonly caseReferences = signal<CaseReference[]>([]);
  protected readonly loadError = signal<string | null>(null);
  protected readonly busy = signal(false);

  protected newCaseRef = {
    title: '',
    url: '',
    consultationId: '' as string,
  };
  protected formError = signal<string | null>(null);

  ngOnInit(): void {
    this.loadHealth();
    this.reloadCaseRefs();
  }

  private loadHealth(): void {
    this.apiStatus.set('Checking…');
    this.health.check().subscribe({
      next: (h) => this.apiStatus.set(h.status),
      error: (e) =>
        this.apiStatus.set(
          e instanceof Error ? e.message : 'unreachable (is the API running on :8000?)',
        ),
    });
  }

  protected reloadCaseRefs(): void {
    this.loadError.set(null);
    this.busy.set(true);
    this.caseRefApi.list().subscribe({
      next: (refs) => {
        this.caseReferences.set(refs);
        this.loadError.set(null);
      },
      error: (e) => {
        this.loadError.set(httpErrorMessage(e));
        this.busy.set(false);
      },
      complete: () => this.busy.set(false),
    });
  }

  protected addCaseReference(): void {
    this.formError.set(null);
    const idRaw = this.newCaseRef.consultationId.trim();
    let consultationId: number | null = null;
    if (idRaw !== '') {
      const n = Number.parseInt(idRaw, 10);
      if (Number.isNaN(n)) {
        this.formError.set('Consultation ID must be a number or empty.');
        return;
      }
      consultationId = n;
    }
    this.busy.set(true);
    this.caseRefApi
      .create({
        title: this.newCaseRef.title,
        url: this.newCaseRef.url,
        consultation_id: consultationId,
      })
      .subscribe({
        next: (row) => {
          this.caseReferences.update((c) => [row, ...c]);
          this.newCaseRef = { title: '', url: '', consultationId: '' };
        },
        error: (e) => {
          this.formError.set(httpErrorMessage(e));
          this.busy.set(false);
        },
        complete: () => this.busy.set(false),
      });
  }
}
