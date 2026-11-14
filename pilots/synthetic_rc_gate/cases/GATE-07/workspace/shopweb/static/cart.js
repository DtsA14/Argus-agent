export function apiBase() {
  if (process.env.NODE_ENV === 'test') {
    return 'http://localhost:0';
  }
  return '/api';
}
