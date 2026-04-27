# MyLegalCompanionUi

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 20.3.24. It calls the **Legal Companion** FastAPI backend (paths such as `/api/consultations`, `/api/case-references`, `/health`).

## Local API

Start the API on port **8000** (from the `backend/api` app). The dev server uses `proxy.conf.json` so the browser can request `/api` and `/health` on the same origin as the Angular app—no CORS changes are required for this setup.

## Development server

To start a local development server, run:

```bash
ng serve
```

Open `http://localhost:4200/`. The **Consultations** screen is at `/consultations` (or use the app nav). The app will reload when you change source files.

**Production** builds use `src/environments/environment.production.ts`. Set `apiBaseUrl` there to your deployed API origin if the UI is not served on the same host as the API, and add that origin to the API `CORS_ORIGINS` list.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Karma](https://karma-runner.github.io) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
