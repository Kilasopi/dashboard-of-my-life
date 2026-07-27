export interface ProgrammingStatus {
  available: boolean;
  message: string | null;
  project_name: string | null;
  branch: string | null;
  commit_hash: string | null;
  commit_message: string | null;
  commit_author: string | null;
  commit_date: string | null;
  changed_files: number | null;
  ahead: number | null;
  behind: number | null;
}
