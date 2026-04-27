import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { apiPath } from '../core/api-path';
import { CaseReference, CaseReferenceCreate } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class CaseReferenceService {
  private readonly http = inject(HttpClient);

  list(offset = 0, limit = 100) {
    const params = new HttpParams()
      .set('offset', String(offset))
      .set('limit', String(limit));
    return this.http.get<CaseReference[]>(apiPath('/api/case-references'), {
      params,
    });
  }

  create(body: CaseReferenceCreate) {
    return this.http.post<CaseReference>(apiPath('/api/case-references'), body);
  }
}
