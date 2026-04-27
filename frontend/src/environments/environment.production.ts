export const environment = {
  production: true,
  apiBaseUrl: '',
  /** Injected in CI: use `pk_live_...` in production. */
  PUBLISHABLE_KEY: '',
  clerkSignInPath: '/sign-in',
  clerkSignUpPath: '/sign-up',
  afterSignInPath: '/home',
  afterSignUpPath: '/home',
} as const;
