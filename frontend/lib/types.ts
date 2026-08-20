export type FieldType =
  | "string"
  | "integer"
  | "float"
  | "boolean"
  | "date"
  | "datetime"
  | "uuid"
  | "enum"
  | "array"
  | "object"
  | "json";

export const FIELD_TYPES: FieldType[] = [
  "string",
  "integer",
  "float",
  "boolean",
  "date",
  "datetime",
  "uuid",
  "enum",
  "array",
  "object",
  "json",
];

export interface EntityField {
  id: string;
  entity_id: string;
  name: string;
  field_type: FieldType;
  order: number;
  required: boolean;
  nullable: boolean;
  unique: boolean;
  default_value: string | null;
  min_value: number | null;
  max_value: number | null;
  regex: string | null;
  enum_values: string[] | null;
}

export interface Entity {
  id: string;
  project_id: string;
  name: string;
  created_at: string;
  fields: EntityField[];
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
}

export interface FieldCreateInput {
  name: string;
  field_type: FieldType;
  required: boolean;
  nullable: boolean;
  unique: boolean;
  min_value?: number | null;
  max_value?: number | null;
  regex?: string | null;
  enum_values?: string[] | null;
}
