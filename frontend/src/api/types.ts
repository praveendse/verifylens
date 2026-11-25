/**
 * Friendly names for the generated OpenAPI types.
 * schema.d.ts is GENERATED (npm run gen:api) — never edit it by hand.
 * If the backend changes a field, regenerate and `npm run typecheck` shows every place that breaks.
 */
import type { components } from './schema';

type Schemas = components['schemas'];

export type User = Schemas['UserPublic'];
export type Role = User['role'];
export type UserCreate = Schemas['UserCreate'];
export type UserUpdate = Schemas['UserUpdate'];

export type HistoryItem = Schemas['HistoryItem'];
export type HistoryDetail = Schemas['HistoryDetail'];
export type HistoryStats = Schemas['HistoryStats'];

export type SearchMode = Schemas['SearchRequest']['mode'];
export type SearchResponse = Schemas['SearchResponse'];
/** What the result view can show: a fresh search result or a saved record. */
export type VerificationResult = SearchResponse & Partial<HistoryDetail>;

export type AdminOverview = Schemas['AdminOverviewResponse'];
export type DailyActivity = Schemas['DailyActivity'];

export type SystemStatus = Schemas['SystemStatusResponse'];
export type ComponentStatus = Schemas['ComponentStatus'];

export type AccessToken = Schemas['AccessToken'];

/** A page of a list endpoint. hasMore comes from asking for one extra row. */
export interface Page<T> {
  items: T[];
  hasMore: boolean;
}

export type HistoryStatusFilter = '' | 'SUCCESS' | 'ERROR' | 'PENDING';
export interface HistoryFilter {
  q: string;
  status: HistoryStatusFilter;
}
