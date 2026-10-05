import type { ApiValidationError } from "./types";

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail: string;
  public readonly errors?: ApiValidationError[];

  constructor(status: number, detail: string, errors?: ApiValidationError[]) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.errors = errors;
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }

  get isValidationError(): boolean {
    return this.status === 422;
  }

  get isServerError(): boolean {
    return this.status >= 500;
  }
}
