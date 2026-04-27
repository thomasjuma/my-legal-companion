export const environment = {
  production: true,
  apiBaseUrl: "nuk4pgpmz9.eu-west-1.awsapprunner.com",
  /** Injected in CI: use `pk_live_...` in production. */
  PUBLISHABLE_KEY: 'pk_test_YWNjZXB0ZWQtY2FyaWJvdS0xNy5jbGVyay5hY2NvdW50cy5kZXYk',
  clerkSignInPath: '/sign-in',
  clerkSignUpPath: '/sign-up',
  afterSignInPath: '/home',
  afterSignUpPath: '/home',
} as const;
