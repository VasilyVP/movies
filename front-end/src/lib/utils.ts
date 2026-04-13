import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

type QueryParamValue = string | number | boolean | null | undefined

type GetFetcherOptions = {
  params?: Record<string, QueryParamValue>
}

function buildApiUrl(path: string, options?: GetFetcherOptions): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  const url = new URL(`/api${normalizedPath}`, window.location.origin)

  if (options?.params) {
    for (const [key, value] of Object.entries(options.params)) {
      if (value === null || value === undefined) {
        continue
      }

      url.searchParams.set(key, String(value))
    }
  }

  return `${url.pathname}${url.search}`
}

export function getFetcher<TResponse>(
  path: string,
  options?: GetFetcherOptions,
): () => Promise<TResponse> {
  return async (): Promise<TResponse> => {
    const response = await fetch(buildApiUrl(path, options))

    if (!response.ok) {
      throw new Error(`Request failed (${response.status})`)
    }

    return (await response.json()) as TResponse
  }
}
