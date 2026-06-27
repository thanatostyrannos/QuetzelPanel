export type Role = "platform-admin" | "customer-admin" | "customer-user";

export interface User {
  id: string;
  username: string;
  role: Role;
  customerId: string | null;
}

export interface Customer {
  id: string;
  name: string;
}
