import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { clerkHttpInterceptor } from './core/clerk-auth.interceptor';
import { provideClerk } from 'ngx-clerk';
import { environment } from '../environments/environment';

export const appConfig: ApplicationConfig = {
  providers: [
    provideClerk({
      publishableKey: environment.PUBLISHABLE_KEY,
      signInUrl: environment.clerkSignInPath,
      signUpUrl: environment.clerkSignUpPath,
    }),
    provideHttpClient(withInterceptors([clerkHttpInterceptor])),
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes)
  ]
};
