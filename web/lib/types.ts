export type PhaseCharacter = "single_phase" | "multi_phase" | "unknown";
export type LinkageStatus = "complete" | "partial" | "ambiguous" | "unlinked";
export type LinkageCertainty = "resolved" | "ambiguous" | "unknown";
export type StructureResolutionLevel = "record" | "group" | "review";

export interface SourceRef {
  code: string;
  source_id?: string | null;
}

export interface Links {
  self?: string | null;
  xy?: string | null;
  cif?: string | null;
  hkl?: string | null;
  patterns?: string | null;
  download?: string | null;
}

export interface Bibliography {
  authors?: string[];
  title?: string | null;
  journal?: string | null;
  year?: string | null;
  volume?: string | null;
  page_first?: string | null;
  page_last?: string | null;
}

export interface Provenance {
  source?: string | null;
  source_id?: string | null;
  source_file?: string | null;
  label_type?: string | null;
  label_method?: string | null;
  evidence?: string | null;
  bibliography?: Bibliography | null;
  notes?: string[];
}

export interface StructureLinkage {
  status: LinkageStatus;
  coverage: "complete" | "partial" | "none";
  certainty: LinkageCertainty;
  candidate_structure_ids: string[];
  resolution_level?: StructureResolutionLevel | null;
}

export interface FractionValue {
  value?: number | null;
  basis?: string | null;
}

export interface PhaseStructure {
  structure_id?: string | null;
  structure_ids: string[];
  status?: string | null;
  coverage?: "complete" | "partial" | "none" | null;
  certainty?: LinkageCertainty | null;
}

export interface PhaseComponent {
  name?: string | null;
  formula?: string | null;
  fraction: FractionValue;
  role?: string | null;
  structure: PhaseStructure;
}

export interface ScanInfo {
  axis?: string | null;
  two_theta_min_deg?: number | null;
  two_theta_max_deg?: number | null;
  point_count?: number | null;
}

export interface RadiationInfo {
  anode?: string | null;
  wavelength_angstrom?: number | null;
  wavelength_kalpha2_angstrom?: number | null;
  wavelengths_angstrom?: number[];
}

export type DatasetRole =
  | "raw"
  | "canonical"
  | "single_phase_precursor"
  | "precursor_mixture_benchmark"
  | "reaction_product_benchmark";

export interface Pattern {
  pattern_id: string;
  measurement_id?: string | null;
  sample_id?: string | null;
  source: SourceRef;
  data_origin: string;
  modality: string;
  dataset_role?: DatasetRole | null;
  phase_character: PhaseCharacter;
  material_label?: string | null;
  phase_components: PhaseComponent[];
  structure_linkage: StructureLinkage;
  structure_resolution_level?: StructureResolutionLevel | null;
  structure_resolution?: {
    resolution_level?: StructureResolutionLevel | null;
  } | null;
  scan: ScanInfo;
  radiation: RadiationInfo;
  provenance: Provenance;
  links: Links;
}

export interface MeasurementConditions {
  anode?: string | null;
  radiation?: string | null;
  wavelength_angstrom?: number | null;
  wavelength_kalpha2_angstrom?: number | null;
  wavelengths_angstrom?: number[];
  scan_range?: number[] | null;
  step_size?: number | null;
  counting_time_seconds?: number | null;
  scan_program?: string | null;
}

export interface Measurement {
  measurement_id: string;
  sample_id?: string | null;
  source: SourceRef;
  modality: string;
  conditions: MeasurementConditions;
  source_file?: string | null;
}

export interface Sample {
  sample_id: string;
  source: SourceRef;
  name?: string | null;
  formula?: string | null;
  phase_character: PhaseCharacter;
}

export interface XYAxis {
  name: string;
  unit: string;
  values: number[];
}

export interface PatternXY {
  pattern_id: string;
  x: XYAxis;
  y: XYAxis;
}

export interface SpaceGroup {
  hm?: string | null;
  number?: number | null;
}

export interface Cell {
  a?: number | null;
  b?: number | null;
  c?: number | null;
  alpha?: number | null;
  beta?: number | null;
  gamma?: number | null;
}

export interface Structure {
  structure_id: string;
  source: SourceRef;
  formula?: string | null;
  formula_normalized?: string | null;
  mineral_name?: string | null;
  space_group: SpaceGroup;
  cell: Cell;
  atom_site_count?: number | null;
  provenance: Provenance;
  links: Links;
}

export interface ReflectionSet {
  reflection_set_id: string;
  measurement_id?: string | null;
  structure_id?: string | null;
  source: SourceRef;
  data_origin: string;
  modality: string;
  reflection_count?: number | null;
  observed_quantity?: string | null;
  available_fields: string[];
  provenance: Provenance;
  links: Links;
}

export interface PageMeta {
  count: number;
  total_count?: number | null;
  next_cursor?: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PageMeta;
}

export interface ApiStats {
  powder_pattern_count?: number;
  single_crystal_dataset_count?: number;
  multiphase_pattern_count?: number;
  structure_count?: number;
  source_count?: number;
  sample_count?: number;
  measurement_count?: number;
  pattern_count?: number;
  reflection_set_count?: number;
  relation_count?: number;
  powbase_xray_pattern_count?: number;
  powder_pattern_counts_by_source?: Record<string, number>;
  phase_character_counts?: Record<string, number>;
  source_phase_counts?: Record<string, Record<string, number>>;
  [key: string]: unknown;
}

export interface SourceCatalogItem {
  source_id?: string;
  api_source_code?: string;
  name?: string;
  short_name?: string;
  source_type?: string;
  data_origin?: string;
  label?: string;
  description?: string;
  modalities?: string[];
  [key: string]: unknown;
}

export interface SearchResponse {
  query: string;
  patterns: Pattern[];
  structures: Structure[];
  samples: Sample[];
  reflection_sets: ReflectionSet[];
}
