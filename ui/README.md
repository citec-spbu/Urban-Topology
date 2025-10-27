# MyApp

This project was generated with [Angular CLI](https://github.com/angular/angular-cli) version 14.2.5.

## Development server

Run `ng serve` for a dev server. Navigate to `http://localhost:4200/`. The application will automatically reload if you change any of the source files.

## Build

### Development Build

```bash
ng build
# Uses environment.ts with localhost API
```

### Production Build

```bash
ng build --configuration production
# Uses environment.prod.ts with production API URL
```

The build artifacts will be stored in the `dist/` directory.

### Environment Configuration

The application uses environment-specific configuration files:

- **Development**: `src/environments/environment.ts` (localhost API)
- **Production**: `src/environments/environment.prod.ts` (production API)

To change the production API URL, edit `src/environments/environment.prod.ts` or use CI/CD environment variables.

## Code scaffolding

Run `ng generate component component-name` to generate a new component. You can also use `ng generate directive|pipe|service|class|guard|interface|enum|module`.

## Running unit tests

Run `ng test` to execute the unit tests via [Karma](https://karma-runner.github.io).

## Running end-to-end tests

Run `ng e2e` to execute the end-to-end tests via a platform of your choice. To use this command, you need to first add a package that implements end-to-end testing capabilities.

## Further help

To get more help on the Angular CLI use `ng help` or go check out the [Angular CLI Overview and Command Reference](https://angular.io/cli) page.
