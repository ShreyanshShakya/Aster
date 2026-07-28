"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const sessionKey = "aster.access-token";

type User = { id: string; email: string; display_name: string };
type Project = { id: string; name: string; description: string | null; created_at: string };
type ResearchRun = { id: string; project_id: string; question: string; status: string; plan: { hypothesis?: string | { statement?: string }; papers?: Array<{ title: string; year: number | null; source: string; score: number }>; experiments?: Array<{ name: string }> } | null; created_at: string };
type Job = { id: string; kind: string; status: string; payload: Record<string, unknown>; result: Record<string, unknown> | null; error: string | null };
type Worker = { id: string; name: string; capabilities: Record<string, string>; last_heartbeat_at: string | null };
type Report = { id: string; research_run_id: string; markdown_artifact_id: string | null; json_artifact_id: string | null };
type JobEvent = { id: string; status: string; message: string; created_at: string };
type Paper = { id: string; title: string; authors: string[]; publication_year: number | null; abstract: string | null; url: string | null; cited_by_count: number };
type ResearchEvent = { id: string; stage: string; message: string; created_at: string };
type LiteratureSynthesis = { summary: string; abstracts_available?: number; papers_ranked?: number; limitations?: string; evidence_excerpts: Array<{ title: string; source: string; score: number; excerpt: string }> };
type ExperimentDesign = { primary_metric: string; baseline: { name: string }; intervention: { name: string }; controls: string[]; acceptance_criterion: string; execution_status: string };
type Executor = { id: string; label: string; available: boolean; evidence_mode: string; description: string };

function jobResultSummary(result: Record<string, unknown>) {
  if (result.mode === "local-plan-validation") return "Local hand-off validated — no model training or benchmark metric was produced.";
  if (result.mode === "real-literature-planning") return `Literature plan completed with ${result.paper_count ?? 0} ranked papers.`;
  if (result.mode === "dmlf") {
    const remote = result.result as Record<string, unknown> | undefined;
    return `DMLF job ${result.remote_job_id ?? "submitted"} completed${remote?.metrics ? " with returned training metrics" : ""}.`;
  }
  return "Job completed with a structured result.";
}
export type WorkspaceView = "projects" | "research" | "jobs" | "workers" | "reports" | "settings";

export function AsterPlatform({ activeView = "research" }: { activeView?: WorkspaceView }) {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [profileName, setProfileName] = useState("");
  const [projectName, setProjectName] = useState("My first research project");
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [question, setQuestion] = useState("How can U-Net improve tumor segmentation?");
  const [researchRuns, setResearchRuns] = useState<ResearchRun[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [queue, setQueue] = useState<Record<string, number>>({});
  const [reports, setReports] = useState<Report[]>([]);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [executors, setExecutors] = useState<Executor[]>([]);
  const [executorId, setExecutorId] = useState("local-plan-validation");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedResearchId, setSelectedResearchId] = useState<string | null>(null);
  const [researchDetails, setResearchDetails] = useState<{ papers: Paper[]; progress: ResearchEvent[]; proposal: { hypothesis: { statement: string; rationale: string; risk: string } | null; experiment_plan: { configuration: Record<string, unknown>; datasets: Array<{ name: string; reason: string }>; metrics: string[]; experiment_design?: ExperimentDesign | null } | null }; synthesis: LiteratureSynthesis } | null>(null);
  const [connected, setConnected] = useState(false);
  const [message, setMessage] = useState("Create an account or sign in to begin.");

  const authenticated = useCallback(async (path: string, options: RequestInit = {}) => {
    const response = await fetch(`${apiBase}${path}`, { ...options, headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(options.headers ?? {}) } });
    if (!response.ok) throw new Error((await response.json()).detail ?? "Request failed");
    return response.json();
  }, [token]);

  const loadWorkspace = useCallback(async () => {
    if (!token) return;
    const [profile, projectList, researchList, jobList, workerList, queueSummary, reportList, executorList] = await Promise.all([
      authenticated("/profile"), authenticated("/projects"), authenticated("/research"), authenticated("/jobs"), authenticated("/workers"), authenticated("/queue"), authenticated("/reports"), authenticated("/executors"),
    ]);
    setUser(profile); setProfileName(profile.display_name); setProjectId((current) => current || projectList[0]?.id || "");
    setProjects(projectList); setResearchRuns(researchList); setJobs(jobList); setWorkers(workerList); setQueue(queueSummary); setReports(reportList); setExecutors(executorList);
  }, [authenticated, token]);

  useEffect(() => { const stored = window.sessionStorage.getItem(sessionKey); if (stored) setToken(stored); }, []);
  useEffect(() => { loadWorkspace().catch((error) => { window.sessionStorage.removeItem(sessionKey); setToken(""); setMessage(error instanceof Error ? error.message : "Your session has expired."); }); }, [loadWorkspace]);
  useEffect(() => {
    if (!token) return;
    const socket = new WebSocket(`${apiBase.replace(/^http/, "ws")}/ws/jobs?token=${encodeURIComponent(token)}`);
    socket.onopen = () => setConnected(true); socket.onclose = () => setConnected(false);
    socket.onmessage = () => { loadWorkspace().catch(() => setMessage("Job changed, but the latest list could not be loaded.")); };
    return () => socket.close();
  }, [loadWorkspace, token]);

  async function authenticate(event: FormEvent, mode: "signup" | "login") {
    event.preventDefault();
    try {
      const body = mode === "signup" ? { email, password, display_name: displayName } : { email, password };
      const response = await fetch(`${apiBase}/auth/${mode}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Authentication failed");
      const data = await response.json(); window.sessionStorage.setItem(sessionKey, data.access_token); setToken(data.access_token); setPassword(""); setMessage(mode === "signup" ? "Account created." : "Signed in.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Authentication failed"); }
  }
  async function createProject() { try { const project = await authenticated("/projects", { method: "POST", body: JSON.stringify({ name: projectName }) }); setProjects((current) => [project, ...current]); setProjectId(project.id); setMessage("Project created."); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not create project"); } }
  async function saveProfile(event: FormEvent) { event.preventDefault(); try { setUser(await authenticated("/profile", { method: "PATCH", body: JSON.stringify({ display_name: profileName }) })); setMessage("Profile saved."); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not save profile"); } }
  async function submitResearch(event: FormEvent) { event.preventDefault(); if (!projectId) return setMessage("Create a project first."); try { await authenticated("/research", { method: "POST", body: JSON.stringify({ project_id: projectId, question }) }); setMessage("Research queued."); await loadWorkspace(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not queue research"); } }
  async function startResearchEngine() { if (!projectId) return setMessage("Create a project first."); try { await authenticated("/research/start", { method: "POST", body: JSON.stringify({ project_id: projectId, question }) }); setMessage("Real literature planning queued. This can take longer than mock planning."); await loadWorkspace(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not start literature planning"); } }
  async function inspectResearch(runId: string) { const results = await Promise.allSettled([authenticated(`/research/${runId}/papers`), authenticated(`/research/${runId}/progress`), authenticated(`/research/${runId}/proposal`), authenticated(`/research/${runId}/synthesis`)]); const [papersResult, progressResult, proposalResult, synthesisResult] = results; const papers = papersResult.status === "fulfilled" ? papersResult.value : []; const progress = progressResult.status === "fulfilled" ? progressResult.value : []; const proposal = proposalResult.status === "fulfilled" ? proposalResult.value : { hypothesis: null, experiment_plan: null }; const synthesis = synthesisResult.status === "fulfilled" ? synthesisResult.value : { summary: "No literature synthesis was returned.", evidence_excerpts: [] }; setSelectedResearchId(runId); setResearchDetails({ papers, progress, proposal, synthesis }); setTimeout(() => document.getElementById("evidence-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0); if (results.some((result) => result.status === "rejected")) setMessage("Some detailed evidence endpoints are unavailable; showing all persisted evidence that could be loaded."); }
  async function validatePlan(runId: string) { try { await authenticated(`/research/${runId}/validate`, { method: "POST", body: JSON.stringify({ executor: executorId }) }); setMessage("Execution job queued. Check its evidence mode before interpreting results."); await loadWorkspace(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not queue execution job"); } }
  async function showTimeline(jobId: string) { try { setSelectedJobId(jobId); setEvents(await authenticated(`/jobs/${jobId}/events`)); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not load timeline"); } }
  async function cancelJob(jobId: string) { try { await authenticated(`/jobs/${jobId}/cancel`, { method: "POST" }); setMessage("Job cancelled."); await loadWorkspace(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not cancel job"); } }
  async function openArtifact(id: string | null) { if (!id) return; try { const response = await fetch(`${apiBase}/artifacts/${id}/content`, { headers: { Authorization: `Bearer ${token}` } }); if (!response.ok) throw new Error("Could not retrieve report"); const url = URL.createObjectURL(await response.blob()); window.open(url, "_blank", "noopener,noreferrer"); setTimeout(() => URL.revokeObjectURL(url), 60_000); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not retrieve report"); } }
  function signOut() { window.sessionStorage.removeItem(sessionKey); setToken(""); setUser(null); setMessage("Signed out."); }

  if (!token) return <main><header><p className="eyebrow">ASTER PLATFORM - MILESTONE 1</p><h1>Research operations, locally reproducible.</h1><p>Question to plan to local worker to report.</p></header><section className="card auth-grid"><form onSubmit={(event) => authenticate(event, "signup")}><h2>Create account</h2><input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Display name" required /><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" type="email" required /><input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password (8+ characters)" type="password" minLength={8} required /><button>Create account</button></form><form onSubmit={(event) => authenticate(event, "login")}><h2>Sign in</h2><input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Email" type="email" required /><input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Password" type="password" required /><button>Sign in</button></form></section><p className="message">{message}</p></main>;

  return <main><header><p className="eyebrow">ASTER PLATFORM - MILESTONE 1</p><div className="row"><h1>Research operations, locally reproducible.</h1><button onClick={signOut}>Sign out</button></div><form className="profile" onSubmit={saveProfile}><label>Signed in as <input value={profileName} onChange={(event) => setProfileName(event.target.value)} /></label><button>Save name</button><span className={connected ? "live" : "offline"}>{connected ? "Live updates connected" : "Reconnecting"}</span></form></header>
    <nav className="workspace-nav"><Link href="/projects">Projects</Link><Link href="/research">Research</Link><Link href="/jobs">Jobs</Link><Link href="/workers">Workers</Link><Link href="/reports">Reports</Link><Link href="/settings">Settings</Link></nav>
    {(activeView === "projects" || activeView === "research") && <section className="card"><h2>Project</h2><div className="inline-form"><input value={projectName} onChange={(event) => setProjectName(event.target.value)} /><button onClick={createProject}>Create project</button></div>{projects.length ? <ul className="project-list">{projects.map((project) => <li key={project.id}><button className={project.id === projectId ? "project active-project" : "project"} onClick={() => setProjectId(project.id)}>{project.name}</button></li>)}</ul> : <p>Create a project before queuing research.</p>}</section>}
    {activeView === "research" && <><section className="card"><h2>New research run</h2><form onSubmit={submitResearch}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={4} /><div className="report-actions"><button disabled={!projectId}>Queue mock research</button><button type="button" onClick={startResearchEngine} disabled={!projectId}>Build real literature proposal</button></div></form></section><section className="card"><h2>Research history</h2>{researchRuns.length ? <ul>{researchRuns.map((run) => { const hypothesis = run.plan?.hypothesis; const summary = typeof hypothesis === "string" ? hypothesis : hypothesis?.statement; const papers = run.plan?.papers ?? []; return <li key={run.id}><strong>{run.status}</strong> - {run.question}<small>{summary ?? "Plan pending worker completion."}</small>{papers.length > 0 && <small>Retrieved evidence: {papers.length} ranked papers from {Array.from(new Set(papers.map((paper) => paper.source))).join(", ")}</small>}<button className="subtle" onClick={() => inspectResearch(run.id)}>View evidence</button></li>; })}</ul> : <p>No research runs yet.</p>}</section>{selectedResearchId && researchDetails && <section id="evidence-panel" className="card"><div className="row"><h2>Evidence and proposal</h2><button className="subtle" onClick={() => setSelectedResearchId(null)}>Close</button></div><h3>Research progress</h3>{researchDetails.progress.length ? <ol>{researchDetails.progress.map((item) => <li key={item.id}><strong>{item.stage}</strong> - {item.message}<small>{new Date(item.created_at).toLocaleString()}</small></li>)}</ol> : <p>No persisted progress events were returned.</p>}<h3>Literature synthesis</h3><p>{researchDetails.synthesis.summary}</p><small>{researchDetails.synthesis.limitations}</small>{researchDetails.synthesis.evidence_excerpts.length > 0 && <ol>{researchDetails.synthesis.evidence_excerpts.map((item) => <li key={`${item.source}-${item.title}`}><strong>{item.title}</strong><small>{item.source} evidence excerpt: {item.excerpt}</small></li>)}</ol>}<h3>Ranked papers</h3>{researchDetails.papers.length ? <ol>{researchDetails.papers.map((paper) => <li key={paper.id}><strong>{paper.title}</strong><small>{paper.publication_year ?? "Unknown year"} - cited by {paper.cited_by_count}</small>{paper.url && <small><a href={paper.url} target="_blank" rel="noreferrer">Source</a></small>}</li>)}</ol> : <p>No detailed paper records were returned. The research history summary above remains the fallback evidence record.</p>}{researchDetails.proposal.hypothesis && <><h3>Hypothesis</h3><p>{researchDetails.proposal.hypothesis.statement}</p><small>{researchDetails.proposal.hypothesis.rationale}</small></>}{researchDetails.proposal.experiment_plan && <><h3>Experiment plan</h3>{researchDetails.proposal.experiment_plan.experiment_design && <><p><strong>Baseline:</strong> {researchDetails.proposal.experiment_plan.experiment_design.baseline.name}</p><p><strong>Intervention:</strong> {researchDetails.proposal.experiment_plan.experiment_design.intervention.name}</p><p><strong>Acceptance:</strong> {researchDetails.proposal.experiment_plan.experiment_design.acceptance_criterion}</p><ul>{researchDetails.proposal.experiment_plan.experiment_design.controls.map((control) => <li key={control}>{control}</li>)}</ul><small>{researchDetails.proposal.experiment_plan.experiment_design.execution_status}</small><label>Execution backend<select value={executorId} onChange={(event) => setExecutorId(event.target.value)}>{executors.map((executor) => <option key={executor.id} value={executor.id} disabled={!executor.available}>{executor.label}{executor.available ? "" : " (not configured)"}</option>)}</select></label><small>{executors.find((executor) => executor.id === executorId)?.description}</small><button className="subtle" disabled={!executors.find((executor) => executor.id === executorId)?.available} onClick={() => validatePlan(selectedResearchId)}>Queue execution</button></>}<pre>{JSON.stringify(researchDetails.proposal.experiment_plan.configuration, null, 2)}</pre><p>Datasets: {researchDetails.proposal.experiment_plan.datasets.map((dataset) => dataset.name).join(", ")}</p><p>Metrics: {researchDetails.proposal.experiment_plan.metrics.join(", ")}</p></>}</section>}</>}
    {activeView === "jobs" && <section className="card"><div className="row"><h2>Jobs</h2><button onClick={() => loadWorkspace()}>Refresh</button></div>{jobs.length ? <ul>{jobs.map((job) => <li key={job.id}><strong>{job.status}</strong> - {job.kind}<small>{job.id}</small>{job.result && <small>{jobResultSummary(job.result)}</small>}{job.error && <small>Worker error: {job.error}</small>}<button className="subtle" onClick={() => showTimeline(job.id)}>View timeline</button>{(["queued", "assigned"].includes(job.status) || (job.status === "running" && job.payload.executor === "dmlf" && Boolean(job.payload.remote_job_id))) && <button className="subtle danger" onClick={() => cancelJob(job.id)}>Cancel</button>}</li>)}</ul> : <p>No jobs yet.</p>}{selectedJobId && <div className="timeline"><div className="row"><h3>Job timeline</h3><button className="subtle" onClick={() => setSelectedJobId(null)}>Close</button></div><ol>{events.map((event) => <li key={event.id}><strong>{event.status}</strong> - {event.message}<small>{new Date(event.created_at).toLocaleString()}</small></li>)}</ol></div>}</section>}
    {activeView === "workers" && <section className="card"><h2>Execution workers</h2><p>Queued: {queue.queued ?? 0} - Running: {queue.running ?? 0} - Completed: {queue.succeeded ?? 0}</p>{workers.length ? <ul>{workers.map((worker) => <li key={worker.id}><strong>{worker.name}</strong> - {Array.isArray(worker.capabilities.executors) ? worker.capabilities.executors.join(", ") : worker.capabilities.executor ?? "worker"}<small>Resource: {worker.capabilities.resource ?? "unspecified"} - Last heartbeat: {worker.last_heartbeat_at ?? "waiting"}</small></li>)}</ul> : <p>No worker heartbeat received.</p>}</section>}
    {activeView === "reports" && <section className="card"><h2>Reports</h2>{reports.length ? <ul>{reports.map((report) => <li key={report.id}>Run {report.research_run_id}<div className="report-actions">{report.markdown_artifact_id && <button onClick={() => openArtifact(report.markdown_artifact_id)}>Open Markdown</button>}{report.json_artifact_id && <button onClick={() => openArtifact(report.json_artifact_id)}>Open JSON</button>}</div></li>)}</ul> : <p>No completed reports yet.</p>}</section>}
    {activeView === "settings" && <section className="card"><h2>Settings</h2><p>Profile and session settings are in the header. Infrastructure settings remain environment-based for Milestone 1.</p></section>}
    <p className="message">{user?.email} - {message}</p></main>;
}

export default function Home() { return <AsterPlatform />; }
