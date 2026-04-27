import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ConsultationService } from '../services/consultation.service';
import { httpErrorMessage } from '../core/http-error-message';
import {
  CONSULTATION_TYPES,
  Consultation,
  ConsultationType,
} from '../models/api.models';

@Component({
  selector: 'app-consultations',
  imports: [CommonModule, FormsModule],
  templateUrl: './consultations.html',
  styleUrl: './consultations.css',
})
export class ConsultationsComponent implements OnInit {
  private readonly api = inject(ConsultationService);

  protected readonly typeOptions = CONSULTATION_TYPES;
  protected readonly rows = signal<Consultation[]>([]);
  protected readonly selected = signal<Consultation | null>(null);
  protected readonly loadError = signal<string | null>(null);
  protected readonly formError = signal<string | null>(null);
  protected readonly busy = signal(false);
  protected readonly listLoading = signal(true);

  protected newConsultation = {
    consultation_type: 'legal' as ConsultationType,
    consultation_query: '',
    consultation_report: '',
    consultation_notes: '',
  };

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

  protected submitNew(): void {
    this.formError.set(null);
    this.busy.set(true);
    this.api
      .create({
        consultation_type: this.newConsultation.consultation_type,
        consultation_query: this.newConsultation.consultation_query,
        consultation_report: this.newConsultation.consultation_report,
        consultation_notes: this.newConsultation.consultation_notes,
      })
      .subscribe({
        next: (row) => {
          this.rows.update((r) => [row, ...r]);
          this.selected.set(row);
          this.newConsultation = {
            consultation_type: 'legal',
            consultation_query: '',
            consultation_report: '',
            consultation_notes: '',
          };
        },
        error: (e) => {
          this.formError.set(httpErrorMessage(e));
          this.busy.set(false);
        },
        complete: () => this.busy.set(false),
      });
  }
}
