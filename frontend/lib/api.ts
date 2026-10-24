export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Options = {
  method?: "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
  body?: unknown;
  /** Send NO cookies. */
  anonymous?: boolean;
};

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? (opts.body ? "POST" : "GET");
  const res = await fetch(`/api${path}`, {
    method,
    headers: opts.body ? { "Content-Type": "application/json" } : undefined,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    credentials: opts.anonymous ? "omit" : "same-origin",
    cache: "no-store",
  });
  if (!res.ok) {
    let message = "Something went wrong. Try again.";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (res.status === 422) message = "Some fields are missing or invalid. Check the form and try again.";
    } catch {}
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export type UserBureau = {
  id: number;
  code: string;
  name: string;
};

export type Me = {
  id: number;
  name: string;
  username: string;
  role: string;
  bureaus?: UserBureau[];
  regions?: string[];
  must_change_password?: boolean;
};

export const homeFor = (role: string) => {
  if (role === "student") return "/student";
  if (role === "teacher") return "/teacher";
  return "/dashboard";
};
