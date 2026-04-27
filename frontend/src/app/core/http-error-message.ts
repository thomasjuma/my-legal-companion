import { HttpErrorResponse } from '@angular/common/http';

export function httpErrorMessage(e: unknown): string {
  if (e instanceof HttpErrorResponse) {
    const d = e.error;
    if (d && typeof d === 'object' && 'detail' in d) {
      const det = (d as { detail?: string }).detail;
      if (typeof det === 'string') return det;
    }
    return e.message;
  }
  if (e instanceof Error) return e.message;
  return 'Request failed';
}
