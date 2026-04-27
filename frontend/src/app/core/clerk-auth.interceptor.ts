import { isPlatformBrowser } from '@angular/common';
import { HttpInterceptorFn } from '@angular/common/http';
import { inject, PLATFORM_ID } from '@angular/core';
import { ClerkService } from 'ngx-clerk';
import { from, switchMap } from 'rxjs';

function isApiPath(url: string): boolean {
  try {
    const u = new URL(url);
    return u.pathname.startsWith('/api/');
  } catch {
    return url.includes('/api/');
  }
}

/**
 * Attaches `Authorization: Bearer <Clerk session token>` to same-origin /api/* requests
 * (matches the FastAPI `clerk_bearer` dependency in the legal companion API).
 */
export const clerkHttpInterceptor: HttpInterceptorFn = (req, next) => {
  if (!isApiPath(req.url)) {
    return next(req);
  }
  if (!isPlatformBrowser(inject(PLATFORM_ID))) {
    return next(req);
  }

  const session = inject(ClerkService).session();
  if (!session) {
    return next(req);
  }

  return from(session.getToken()).pipe(
    switchMap((token) => {
      if (!token) {
        return next(req);
      }
      return next(
        req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }),
      );
    }),
  );
};
