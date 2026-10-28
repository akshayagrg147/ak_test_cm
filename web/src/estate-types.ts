import type { FileItem, Organization } from "./types";

export interface Property {
  id: string;
  title: string;
  reference: string;
  project: string;
  developer: string;
  property_type: string;
  listing_type: string;
  city: string;
  locality: string;
  address: string;
  price: string;
  area_sqft: string;
  bedrooms: number | null;
  bathrooms: number | null;
  possession: string;
  rera_number: string;
  description: string;
  amenities: string[];
  status: string;
  files: FileItem[];
}
export interface Requirement {
  purpose: string;
  budget_min: string;
  budget_max: string | null;
  city: string;
  localities: string[];
  property_types: string[];
  bedrooms: number | null;
  timeline: string;
  financing: string;
  notes: string;
}
export interface Visit {
  id: string;
  lead_id: string;
  lead_name: string;
  property_id: string;
  property_title: string;
  property_reference: string;
  assignee_id: string;
  assignee_name: string;
  starts_at: string;
  actual_started_at: string | null;
  duration_minutes: number;
  status: string;
  notes: string;
  feedback: string;
  field_handoff_id?: string | null;
}
export interface FieldHandoff {
  id: string;
  lead_id: string;
  lead_name: string;
  lead_phone: string;
  executive_id: string;
  executive_name: string;
  coordinator_name: string;
  created_by_name: string;
  status:
    | "pending"
    | "accepted"
    | "follow_up"
    | "ready_for_booking"
    | "closed"
    | "cancelled";
  current: boolean;
  brief: string;
  meeting_point: string;
  property_address: string;
  feedback: string;
  next_action: string;
  follow_up_at: string | null;
  accepted_at: string | null;
  updated_at: string;
  version: number;
  visit: Visit;
}
export interface Booking {
  id: string;
  lead_id: string;
  lead_name: string;
  property_id: string;
  property_title: string;
  agent_id: string;
  agent_name: string;
  reference: string;
  agreed_price: string;
  token_amount: string;
  commission: string;
  status: string;
  booked_on: string;
  notes: string;
}
export interface Plan {
  id: string;
  name: string;
  description: string;
  monthly_price: string;
  yearly_price: string;
  seats: number;
  active: boolean;
}
export interface Subscription {
  id: string;
  plan_id: string | null;
  plan_name: string;
  cycle: string;
  amount: string;
  seats: number;
  used_seats: number;
  status: string;
  effective_status: string;
  starts_on: string;
  ends_on: string;
}
export interface Payment {
  id: string;
  org_id: string;
  company_name?: string;
  plan_id: string;
  plan_name: string;
  cycle: string;
  amount: string;
  seats: number;
  reference: string | null;
  payment_method: "upi" | "cod";
  status: string;
  receipt_id: string | null;
  review_note: string;
  created_at: string;
}
export interface BillingConfig {
  payee_name: string;
  upi_id: string;
  instructions: string;
  qr_ready: boolean;
  upi_enabled: boolean;
  cod_enabled: boolean;
  cod_instructions: string;
}
export interface BillingData {
  subscription: Subscription | null;
  plans: Plan[];
  payments: Payment[];
  config: BillingConfig;
}
export interface Company extends Organization {
  subscription: Subscription | null;
}
export interface CompanyProfile {
  contact_name?: string;
  email?: string;
  phone?: string;
  address?: string;
  city?: string;
  state?: string;
  website?: string;
  rera_number?: string;
  gst_number?: string;
}
