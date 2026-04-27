import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { apiPath } from '../core/api-path';
import { Consultation } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class ConsultationService {
  private readonly http = inject(HttpClient);

  list(offset = 0, limit = 100) {
    const params = new HttpParams()
      .set('offset', String(offset))
      .set('limit', String(limit));
    return this.http.get<Consultation[]>(apiPath('/api/consultations'), {
      params,
    });
  }
}
