import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ConsultationService } from '../services/consultation.service';
import { httpErrorMessage } from '../core/http-error-message';
import { Consultation } from '../models/api.models';

@Component({
  selector: 'app-consultations',
  imports: [CommonModule],
  templateUrl: './consultations.html',
  styleUrl: './consultations.css',
})
export class ConsultationsComponent implements OnInit {
  private readonly api = inject(ConsultationService);

  protected readonly rows = signal<Consultation[]>([]);
  protected readonly selected = signal<Consultation | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly listLoading = signal(true);

  ngOnInit(): void {
    this.reload();
  }

  protected reload(): void {
    this.loadError.set(null);
    this.listLoading.set(true);
    this.api.list().subscribe({
      next: (data) => {
        this.rows.set(data);
        const cur = this.selected();
        if (cur) {
          const found = data.find((r) => r.id === cur.id);
          this.selected.set(found ?? null);
        }
      },
      error: (e) => {
        this.loadError.set(httpErrorMessage(e));
        this.listLoading.set(false);
      },
      complete: () => this.listLoading.set(false),
    });
  }

  protected select(c: Consultation): void {
    this.selected.update((s) => (s?.id === c.id ? null : c));
  }
}
