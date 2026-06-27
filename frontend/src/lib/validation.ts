// A Kubernetes resource name must be a DNS-1123 label: lowercase alphanumerics
// and '-', 1–32 chars, starting and ending alphanumeric. Mirrors the backend's
// CreateServerRequest validator so the UI rejects bad names before the API does.
const DNS_1123_LABEL = /^[a-z0-9]([-a-z0-9]{0,30}[a-z0-9])?$/;

export function isValidServerName(name: string): boolean {
  return DNS_1123_LABEL.test(name);
}
