import { FormEvent, useEffect, useRef, useState } from "react";
import { api, Issue, Project, Status } from "./api";
const statuses: Status[] = ["todo", "in_progress", "done"];
const labels: Record<Status, string> = {
  todo: "To do",
  in_progress: "In progress",
  done: "Done",
};
const message = (error: unknown) =>
  error instanceof Error ? error.message : "Something went wrong.";
const json = (body: object): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
});
export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [project, setProject] = useState<Project | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [filter, setFilter] = useState<Status | "all">("all");
  const [selected, setSelected] = useState<Issue | null>(null);
  const [creatingProject, setCreatingProject] = useState(false);
  const [creatingIssue, setCreatingIssue] = useState(false);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const detailSeq = useRef(0);
  const changeProject = (id: string) => {
    if (id === projectId) return;
    detailSeq.current++;
    setProjectId(id);
    setProject(null);
    setIssues([]);
    setSelected(null);
    setDetailLoading(false);
    setCreatingIssue(false);
    setFilter("all");
    setError("");
    setDetailError("");
  };
  useEffect(() => {
    const controller = new AbortController();
    api<Project[]>("/projects", { signal: controller.signal })
      .then((p) => {
        if (!controller.signal.aborted)
          setProjects((old) => [
            ...p,
            ...old.filter(
              (existing) => !p.some((item) => item.id === existing.id),
            ),
          ]);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(message(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setProjectsLoading(false);
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!projectId) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setIssues([]);
    setProject(null);
    Promise.all([
      api<Project>(`/projects/${projectId}`, { signal: controller.signal }),
      api<Issue[]>(
        `/projects/${projectId}/issues${filter === "all" ? "" : `?status=${filter}`}`,
        { signal: controller.signal },
      ),
    ])
      .then(([p, list]) => {
        if (!controller.signal.aborted) {
          setProject(p);
          setIssues(list);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(message(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [projectId, filter, refresh]);
  async function openIssue(id: string) {
    const sequence = ++detailSeq.current;
    setSelected(null);
    setDetailError("");
    setDetailLoading(true);
    setCreatingIssue(false);
    try {
      const issue = await api<Issue>(`/issues/${id}`);
      if (sequence === detailSeq.current) setSelected(issue);
    } catch (e) {
      if (sequence === detailSeq.current) setDetailError(message(e));
    } finally {
      if (sequence === detailSeq.current) setDetailLoading(false);
    }
  }
  function closeDetail() {
    detailSeq.current++;
    setSelected(null);
    setCreatingIssue(false);
    setDetailLoading(false);
    setDetailError("");
  }
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">◈</span>
          <div>
            mini jira<small>YOUR WORKSPACE</small>
          </div>
        </div>
        <div className="side-heading">
          PROJECTS{" "}
          <button
            className="icon-button"
            aria-label="Create project"
            onClick={() => {
              closeDetail();
              setCreatingProject(true);
            }}
          >
            ＋
          </button>
        </div>
        {projectsLoading && <p className="muted">Loading projects…</p>}
        {!projectsLoading && !projects.length && (
          <p className="muted">No projects yet. Create one to get started.</p>
        )}
        <nav aria-label="Projects">
          {projects.map((p) => (
            <button
              key={p.id}
              className={`project-link ${projectId === p.id ? "active" : ""}`}
              onClick={() => {
                setCreatingProject(false);
                changeProject(p.id);
              }}
            >
              <span className="project-avatar">{p.key.slice(0, 2)}</span>
              <span>
                {p.name}
                <small>{p.key}</small>
              </span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">A little space for big ideas.</div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            Workspace <span className="crumb">/</span>{" "}
            {project?.name || "Projects"}
          </span>
          <span className="top-note">MINI JIRA</span>
        </header>
        <div className="content">
          {error && (
            <div role="alert" className="alert">
              {error}
            </div>
          )}
          {creatingProject ? (
            <ProjectForm
              onCancel={() => setCreatingProject(false)}
              onCreated={(p) => {
                setProjects((old) => [...old, p]);
                setCreatingProject(false);
                changeProject(p.id);
              }}
            />
          ) : !projectId ? (
            <div className="welcome">
              <span className="eyebrow">WELCOME TO YOUR WORKSPACE</span>
              <h1>Make progress, together.</h1>
              <p>
                Keep your projects organized and move work forward, one issue at
                a time.
              </p>
              <button
                className="primary"
                onClick={() => setCreatingProject(true)}
              >
                ＋ Create a project
              </button>
            </div>
          ) : (
            <>
              {loading ? (
                <p role="status">Loading project and issues…</p>
              ) : (
                project && (
                  <>
                    <div className="page-heading">
                      <div>
                        <span className="eyebrow">PROJECT / {project.key}</span>
                        <h1>{project.name}</h1>
                        {project.description && (
                          <p className="description">{project.description}</p>
                        )}
                      </div>
                      <button
                        className="primary"
                        onClick={() => {
                          closeDetail();
                          setCreatingIssue(true);
                        }}
                      >
                        ＋ Create issue
                      </button>
                    </div>
                    <div className="board-header">
                      <div>
                        <h2>Board</h2>
                        <p>Track work from start to finish.</p>
                      </div>
                      <label className="filter">
                        Status{" "}
                        <select
                          value={filter}
                          onChange={(e) => {
                            closeDetail();
                            setFilter(e.target.value as Status | "all");
                          }}
                        >
                          <option value="all">All statuses</option>
                          {statuses.map((s) => (
                            <option key={s} value={s}>
                              {labels[s]}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="board">
                      {statuses
                        .filter((s) => filter === "all" || filter === s)
                        .map((s) => (
                          <section
                            className="column"
                            key={s}
                            aria-label={`${labels[s]} issues`}
                          >
                            <div className="column-heading">
                              <span className={`dot ${s}`} />
                              {labels[s]}{" "}
                              <span className="count">
                                {issues.filter((i) => i.status === s).length}
                              </span>
                            </div>
                            {issues
                              .filter((i) => i.status === s)
                              .map((issue) => (
                                <button
                                  className="issue-card"
                                  key={issue.id}
                                  onClick={() => openIssue(issue.id)}
                                >
                                  <strong>{issue.title}</strong>
                                  {issue.description && (
                                    <span>{issue.description}</span>
                                  )}
                                  <small>View issue →</small>
                                </button>
                              ))}
                            {!issues.some((i) => i.status === s) && (
                              <div className="empty">No issues here yet.</div>
                            )}
                          </section>
                        ))}
                    </div>
                  </>
                )
              )}
              {(creatingIssue || selected || detailLoading || detailError) && (
                <div className="detail">
                  <button
                    className="close"
                    onClick={closeDetail}
                    aria-label="Close issue details"
                  >
                    ×
                  </button>
                  {detailLoading && <p role="status">Loading issue…</p>}
                  {detailError && (
                    <div role="alert" className="alert">
                      {detailError}
                    </div>
                  )}
                  {creatingIssue && (
                    <IssueForm
                      key={`new-${projectId}`}
                      projectId={projectId}
                      onCancel={closeDetail}
                      onSaved={() => {
                        closeDetail();
                        setRefresh((n) => n + 1);
                      }}
                    />
                  )}
                  {selected && (
                    <IssueForm
                      key={selected.id}
                      issue={selected}
                      projectId={projectId}
                      onCancel={closeDetail}
                      onSaved={(issue) => {
                        setSelected(issue);
                        setRefresh((n) => n + 1);
                      }}
                    />
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
function ProjectForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (p: Project) => void;
}) {
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const locked = useRef(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api<Project>(
        "/projects",
        json({ key, name: name.trim(), description }),
      );
      if (active.current) onCreated(result);
    } catch (e) {
      if (active.current) setError(message(e));
    } finally {
      locked.current = false;
      if (active.current) setBusy(false);
    }
  }
  return (
    <section className="form-panel">
      <span className="eyebrow">NEW PROJECT</span>
      <h1>Create a project</h1>
      <p>Give your work a place to live.</p>
      <form onSubmit={submit}>
        {error && (
          <div role="alert" className="alert">
            {error}
          </div>
        )}
        <label>
          Project name
          <input
            required
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          Project key
          <input
            required
            minLength={2}
            maxLength={10}
            pattern="[A-Z]{2,10}"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            aria-describedby="key-help"
          />
          <small id="key-help">
            2–10 uppercase letters. Keys cannot be changed.
          </small>
        </label>
        <label>
          Description <span className="optional">optional</span>
          <textarea
            maxLength={5000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <div className="actions">
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Creating…" : "Create project"}
          </button>
        </div>
      </form>
    </section>
  );
}
function IssueForm({
  issue,
  projectId,
  onCancel,
  onSaved,
}: {
  issue?: Issue;
  projectId: string;
  onCancel: () => void;
  onSaved: (issue: Issue) => void;
}) {
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  const [title, setTitle] = useState(issue?.title || "");
  const [description, setDescription] = useState(issue?.description || "");
  const [status, setStatus] = useState<Status>(issue?.status || "todo");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const locked = useRef(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      const body = { title: title.trim(), description, status };
      const saved = issue
        ? await api<Issue>(`/issues/${issue.id}`, {
            method: "PATCH",
            body: JSON.stringify(body),
          })
        : await api<Issue>(`/projects/${projectId}/issues`, json(body));
      if (active.current) onSaved(saved);
    } catch (e) {
      if (active.current) setError(message(e));
    } finally {
      locked.current = false;
      if (active.current) setBusy(false);
    }
  }
  return (
    <section>
      <span className="eyebrow">{issue ? "ISSUE DETAILS" : "NEW ISSUE"}</span>
      <h2>{issue ? "Edit issue" : "Create issue"}</h2>
      <form onSubmit={submit}>
        {error && (
          <div role="alert" className="alert">
            {error}
          </div>
        )}
        <label>
          Title
          <input
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label>
          Description <span className="optional">optional</span>
          <textarea
            maxLength={10000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label>
          Status
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as Status)}
          >
            {statuses.map((s) => (
              <option key={s} value={s}>
                {labels[s]}
              </option>
            ))}
          </select>
        </label>
        <div className="actions">
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
          <button className="primary" disabled={busy}>
            {busy ? "Saving…" : issue ? "Save changes" : "Create issue"}
          </button>
        </div>
      </form>
    </section>
  );
}
