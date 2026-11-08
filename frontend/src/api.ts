export type Status = "todo" | "in_progress" | "done";
export type Project = {
  id: string;
  key: string;
  name: string;
  description: string;
  created_at: string;
};
export type Issue = {
  id: string;
  project_id: string;
  title: string;
  description: string;
  status: Status;
  created_at: string;
  updated_at: string;
};
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = (await response.json()).detail;
    } catch {
      /* non-JSON response */
    }
    if (response.status === 409)
      throw new Error(
        typeof detail === "string" ? detail : "Project key already exists.",
      );
    if (response.status === 404)
      throw new Error(
        typeof detail === "string"
          ? detail
          : "This resource could not be found.",
      );
    if (response.status === 422) {
      const messages = Array.isArray(detail)
        ? detail
            .map(
              (item: { loc?: string[]; msg?: string }) =>
                `${item.loc?.slice(1).join(".") || "Input"}: ${item.msg || "Invalid value"}`,
            )
            .join("; ")
        : "Please check your input.";
      throw new Error(`Validation error: ${messages}`);
    }
    throw new Error(
      typeof detail === "string"
        ? detail
        : `Request failed (${response.status}).`,
    );
  }
  return response.json() as Promise<T>;
}
