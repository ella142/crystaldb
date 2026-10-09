export interface DownloadAction {
  id: string;
  group: string;
  label: string;
  filename: string;
  url: string;
}

export interface BundleAction {
  id: string;
  label: string;
  filename: string;
  onDownload: () => Promise<void>;
}

export interface BundleResource {
  name: string;
  url: string;
  label: string;
  required?: boolean;
  manifestRecordId?: string;
}
