export const environment = {
  production: false,
  /** Set to a full base URL in production, e.g. https://api.example.com, or "" to use the same origin. */
  apiBaseUrl: '',
  /**
   * Clerk publishable key (safe in the browser).
   * From the Clerk dashboard: https://dashboard.clerk.com/ → your app → API Keys.
   * Never add the Secret Key here; use it only on a backend.
   */
  PUBLISHABLE_KEY: 'pk_test_YWNjZXB0ZWQtY2FyaWJvdS0xNy5jbGVyay5hY2NvdW50cy5kZXYk',
  /** Path where `<clerk-sign-in>` is hosted (match Clerk Dashboard → Paths / authorized redirect URLs). */
  clerkSignInPath: '/sign-in',
  /** Path where `<clerk-sign-up>` is hosted. */
  clerkSignUpPath: '/sign-up',
  /** After successful sign-in / sign-up, navigate here unless the route guard set a return URL. */
  afterSignInPath: '/dashboard',
  afterSignUpPath: '/dashboard',
} as const;
