import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { apiPath } from '../core/api-path';
import { HealthResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class HealthService {
  private readonly http = inject(HttpClient);

  check() {
    return this.http.get<HealthResponse>(apiPath('/health'));
  }
}
