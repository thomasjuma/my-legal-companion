import { environment } from '../../environments/environment';

/**
 * Resolves a path (e.g. /api/consultations) for HttpClient, honoring {@link environment.apiBaseUrl}.
 */
export function apiPath(relative: string): string {
  const normalized = relative.startsWith('/') ? relative : `/${relative}`;
  const base = environment.apiBaseUrl.trim().replace(/\/$/, '');
  return base ? `${base}${normalized}` : normalized;
}
