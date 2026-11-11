export interface Device {
  k_number: string; device_name: string; applicant: string | null; product_code: string;
  decision_date: string | null; decision: string | null; clearance_type: string | null; source: string;
}
export interface Citation { passage_id: number; quote: string; doc_id: string; doc_title: string; page: number }
export interface Passage { id: number; doc_id: string; doc_title: string; page: number; text: string }
export interface RouteStep { model: string; verified: boolean; problems: string[] }
export interface AskResult {
  found: boolean; answer: string; citations: Citation[]; verified: boolean;
  route: RouteStep[]; passages: Passage[]; note?: string;
}
