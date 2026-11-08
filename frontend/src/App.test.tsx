import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App";

const project = {
  id: "p1",
  key: "ONE",
  name: "First",
  description: " First description ",
  created_at: "2024-01-01",
};
const second = { ...project, id: "p2", key: "TWO", name: "Second" };
const issue = {
  id: "i1",
  project_id: "p1",
  title: "Task",
  description: "  notes\n",
  status: "todo",
  created_at: "2024-01-01",
  updated_at: "2024-01-01",
};
const response = (data: unknown, status = 200) =>
  ({ ok: status < 400, status, json: async () => data }) as Response;
afterEach(() => vi.unstubAllGlobals());

test("creates a project, preserves descriptions and shows conflict feedback", async () => {
  const fetcher = vi.fn(async (url: string, opts?: RequestInit) => {
    if (url === "/api/v1/projects" && opts?.method === "POST")
      return response({ detail: "Project key already exists" }, 409);
    return response([]);
  });
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: /create a project/i }),
  );
  fireEvent.change(screen.getByLabelText("Project name"), {
    target: { value: "  Example  " },
  });
  fireEvent.change(screen.getByLabelText(/Project key/), {
    target: { value: "EX" },
  });
  fireEvent.change(screen.getByLabelText(/Description/), {
    target: { value: "  text  " },
  });
  fireEvent.click(screen.getAllByRole("button", { name: "Create project" })[1]);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Project key already exists",
  );
  const post = fetcher.mock.calls.find(([, opts]) => opts?.method === "POST")!;
  expect(JSON.parse(post[1]!.body as string)).toEqual({
    key: "EX",
    name: "Example",
    description: "  text  ",
  });
  expect(fetcher.mock.calls.every(([url]) => url.startsWith("/api/"))).toBe(
    true,
  );
});

test("creates, views and edits issues and filters by status", async () => {
  let current = { ...issue };
  const fetcher = vi.fn(async (url: string, opts?: RequestInit) => {
    if (url === "/api/v1/projects") return response([project]);
    if (url === "/api/v1/projects/p1") return response(project);
    if (url.startsWith("/api/v1/projects/p1/issues")) {
      if (opts?.method === "POST") {
        current = { ...current, ...JSON.parse(opts.body as string) };
        return response(current, 201);
      }
      return response(
        url.includes("?status=done") && current.status !== "done"
          ? []
          : [current],
      );
    }
    if (url === "/api/v1/issues/i1") {
      if (opts?.method === "PATCH")
        current = { ...current, ...JSON.parse(opts.body as string) };
      return response(current);
    }
    throw new Error(url);
  });
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /First/ }));
  fireEvent.click(await screen.findByRole("button", { name: /Task/ }));
  expect(await screen.findByLabelText(/Description/)).toHaveValue("  notes\n");
  fireEvent.change(
    screen.getByLabelText("Status", { selector: "form select" }),
    { target: { value: "done" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([, opts]) => opts?.method === "PATCH"),
    ).toBe(true),
  );
  expect(
    JSON.parse(
      fetcher.mock.calls.find(([, o]) => o?.method === "PATCH")![1]!
        .body as string,
    ),
  ).toMatchObject({ status: "done", description: "  notes\n" });
  fireEvent.click(screen.getByRole("button", { name: "Close issue details" }));
  fireEvent.change(await screen.findByLabelText("Status"), {
    target: { value: "done" },
  });
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(([url]) => url.endsWith("?status=done")),
    ).toBe(true),
  );
  expect(
    await screen.findByRole("region", { name: "Done issues" }),
  ).toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: /Create issue/ }));
  fireEvent.change(screen.getByLabelText("Title"), {
    target: { value: "  New task  " },
  });
  fireEvent.change(screen.getByLabelText(/Description/), {
    target: { value: "  body  " },
  });
  fireEvent.click(screen.getByRole("button", { name: /^Create issue$/ }));
  await waitFor(() =>
    expect(fetcher.mock.calls.some(([, o]) => o?.method === "POST")).toBe(true),
  );
  expect(
    JSON.parse(
      fetcher.mock.calls.find(([, o]) => o?.method === "POST")![1]!
        .body as string,
    ),
  ).toMatchObject({ title: "New task", description: "  body  " });
  expect(fetcher.mock.calls.every(([url]) => url.startsWith("/api/"))).toBe(
    true,
  );
});

test("ignores stale project responses after switching projects", async () => {
  let resolveOld!: (r: Response) => void;
  const old = new Promise<Response>((resolve) => {
    resolveOld = resolve;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url === "/api/v1/projects")
        return Promise.resolve(response([project, second]));
      if (url === "/api/v1/projects/p1") return old;
      if (url === "/api/v1/projects/p1/issues")
        return Promise.resolve(response([issue]));
      if (url === "/api/v1/projects/p2")
        return Promise.resolve(response(second));
      if (url === "/api/v1/projects/p2/issues")
        return Promise.resolve(response([]));
      throw new Error(url);
    }),
  );
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /First/ }));
  fireEvent.click(screen.getByRole("button", { name: /Second/ }));
  expect(
    await screen.findByRole("heading", { name: "Second" }),
  ).toBeInTheDocument();
  resolveOld(response(project));
  await waitFor(() =>
    expect(screen.queryByText("Task")).not.toBeInTheDocument(),
  );
});

test.each([
  [404, "Issue not found"],
  [422, "Validation error"],
])("shows API errors (%i)", async (status, expected) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url === "/api/v1/projects"
        ? response([project])
        : response(
            {
              detail:
                status === 404
                  ? "Issue not found"
                  : [{ loc: ["query", "status"], msg: "Invalid status" }],
            },
            status,
          ),
    ),
  );
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /First/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    expected as string,
  );
});

test("creates a project and disables duplicate submissions while pending", async () => {
  let finish!: (result: Response) => void;
  const pending = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  const fetcher = vi.fn((url: string, opts?: RequestInit) => {
    if (url === "/api/v1/projects" && opts?.method === "POST") return pending;
    if (url === "/api/v1/projects") return Promise.resolve(response([]));
    if (url === "/api/v1/projects/p1")
      return Promise.resolve(response(project));
    if (url === "/api/v1/projects/p1/issues")
      return Promise.resolve(response([]));
    throw new Error(url);
  });
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: /create a project/i }),
  );
  fireEvent.change(screen.getByLabelText("Project name"), {
    target: { value: "First" },
  });
  fireEvent.change(screen.getByLabelText(/Project key/), {
    target: { value: "ONE" },
  });
  fireEvent.click(screen.getAllByRole("button", { name: "Create project" })[1]);
  expect(screen.getByRole("button", { name: "Creating…" })).toBeDisabled();
  expect(
    fetcher.mock.calls.filter(([, opts]) => opts?.method === "POST"),
  ).toHaveLength(1);
  finish(response(project, 201));
  expect(
    await screen.findByRole("heading", { name: "First" }),
  ).toBeInTheDocument();
});
