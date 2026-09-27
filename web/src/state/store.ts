import { create } from "zustand";
import type { AnalysisSections, Depth, JobStatus } from "../api/types";
import { type GraphModel, emptyGraph } from "../graph/model";

export interface JobState {
  id: string;
  kind: "trace" | "cluster" | "analysis";
  status: JobStatus;
  nodes: number;
  stops: number;
  error: string | null;
  reason: string | null;
  calls: number | null;
  /** Epoch ms when the job was started and when it ended (any final status). */
  started: number;
  finished: number | null;
  /** Stages the job reported finished, in order (an analysis: profile, cluster, backward, forward). */
  stages: string[];
}

export interface AnalysisState { address: string; depth: Depth; sections: AnalysisSections; markdown: string | null }

interface Data {
  graph: GraphModel;
  selected: string | null;
  groupClusters: boolean;
  caseId: string | null;
  caseName: string;
  notes: string;
  dirty: boolean;
  /** Changed by the user (not only by a job's graph events) since the last save. */
  edited: boolean;
  job: JobState | null;
  busy: number;
  error: string | null;
  message: string | null;
  analysis: AnalysisState | null;
}

export interface WorkbenchState extends Data {
  updateGraph: (fn: (g: GraphModel) => GraphModel, byJob?: boolean) => void;
  select: (id: string | null) => void;
  setError: (msg: string | null) => void;
  setMessage: (msg: string | null) => void;
  setJob: (job: JobState | null) => void;
  patchJob: (patch: Partial<JobState>) => void;
  begin: () => void;
  end: () => void;
  setGroupClusters: (value: boolean) => void;
  setCase: (c: { id: string | null; name: string; notes: string; graph?: GraphModel }) => void;
  setCaseName: (name: string) => void;
  setNotes: (notes: string) => void;
  markClean: () => void;
  reset: () => void;
  setAnalysis: (analysis: AnalysisState | null) => void;
  patchAnalysis: (patch: Partial<AnalysisState>) => void;
  patchSections: (patch: AnalysisSections) => void;
}

const initial = (): Data => ({
  graph: emptyGraph(), selected: null, groupClusters: true, caseId: null, caseName: "", notes: "",
  dirty: false, edited: false, job: null, busy: 0, error: null, message: null, analysis: null,
});

export const useWorkbench = create<WorkbenchState>()((set) => ({
  ...initial(),
  updateGraph: (fn, byJob = false) => set((s) => ({ graph: fn(s.graph), dirty: true, edited: s.edited || !byJob })),
  select: (id) => set({ selected: id }),
  setError: (error) => set({ error }),
  setMessage: (message) => set({ message }),
  setJob: (job) => set({ job }),
  patchJob: (patch) => set((s) => (s.job ? { job: { ...s.job, ...patch } } : {})),
  begin: () => set((s) => ({ busy: s.busy + 1 })),
  end: () => set((s) => ({ busy: Math.max(0, s.busy - 1) })),
  setGroupClusters: (groupClusters) => set({ groupClusters }),
  setCase: ({ id, name, notes, graph }) =>
    set((s) => ({ caseId: id, caseName: name, notes, graph: graph ?? s.graph, selected: null })),
  setCaseName: (caseName) => set({ caseName, dirty: true, edited: true }),
  setNotes: (notes) => set({ notes, dirty: true, edited: true }),
  markClean: () => set({ dirty: false, edited: false }),
  reset: () => set(initial()),
  setAnalysis: (analysis) => set({ analysis }),
  patchAnalysis: (patch) => set((s) => (s.analysis ? { analysis: { ...s.analysis, ...patch } } : {})),
  patchSections: (patch) =>
    set((s) => (s.analysis ? { analysis: { ...s.analysis, sections: { ...s.analysis.sections, ...patch } } } : {})),
}));
