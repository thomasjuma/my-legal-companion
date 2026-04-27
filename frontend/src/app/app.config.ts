import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { clerkHttpInterceptor } from './core/clerk-auth.interceptor';
import { provideClerk } from 'ngx-clerk';
import { environment } from '../environments/environment';

const publishableKey = environment.PUBLISHABLE_KEY?.trim();
if (!publishableKey) {
  throw new Error(
    'PUBLISHABLE_KEY is empty. Set it in src/environments/environment.ts and ' +
      'src/environments/environment.production.ts (Clerk Dashboard → API Keys → Publishable key).',
  );
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideClerk({
      publishableKey,
      signInUrl: environment.clerkSignInPath,
      signUpUrl: environment.clerkSignUpPath,
    }),
    provideHttpClient(withInterceptors([clerkHttpInterceptor])),
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes)
  ]
};
