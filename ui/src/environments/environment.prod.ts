export const environment = {
  production: true,
  // Production API URL - update this with your actual production API endpoint
  // You can override this via environment variables in your CI/CD pipeline
  apiUrl: 'http://158.160.17.229:8901/api',
};

// Deprecated: Use environment.apiUrl instead
export const host = environment.apiUrl;
