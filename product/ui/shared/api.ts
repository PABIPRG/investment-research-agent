export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message)
  }
}
/** Fixed product-relative routes only; authentication remains with DSH. */
export async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`api/huohuo/${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
    cache: 'no-store',
  })
  const data = await response.json()
  if (!response.ok)
    throw new ApiError(
      response.status === 403
        ? '无权访问此实例，请重新连接。'
        : data.detail || '暂时无法完成，请重试。',
      response.status,
    )
  return data as T
}
export const errorText = (error: unknown) =>
  error instanceof Error ? error.message : '暂时无法完成，请重试。'
