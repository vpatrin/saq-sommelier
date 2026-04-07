import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api, ApiError, fetchAllPages, API_PAGE_SIZE } from './api'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  fetchMock.mockReset()
})

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(body),
  } as Response
}

describe('ApiError', () => {
  it('exposes status and detail', () => {
    const err = new ApiError(404, 'Not found')
    expect(err.status).toBe(404)
    expect(err.detail).toBe('Not found')
    expect(err.message).toBe('Not found')
    expect(err).toBeInstanceOf(Error)
  })
})

describe('api', () => {
  it('returns parsed JSON on success', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ id: 1 }))

    const result = await api('/wines')
    expect(result).toEqual({ id: 1 })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/wines',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    )
  })

  it('attaches Authorization header when token provided', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))

    await api('/wines', { token: 'jwt-123' })
    const headers = fetchMock.mock.calls[0][1].headers
    expect(headers['Authorization']).toBe('Bearer jwt-123')
  })

  it('omits Authorization header when no token', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))

    await api('/wines')
    const headers = fetchMock.mock.calls[0][1].headers
    expect(headers['Authorization']).toBeUndefined()
  })

  it('returns undefined for 204 No Content', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      statusText: 'No Content',
    } as Response)

    const result = await api('/watches/1', { method: 'DELETE' })
    expect(result).toBeUndefined()
  })

  it('throws ApiError with status and detail from response body', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'SKU not found' }, 404))

    await expect(api('/wines/invalid')).rejects.toMatchObject({
      status: 404,
      detail: 'SKU not found',
    })
  })

  it('falls back to statusText when response body has no detail', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('no body')),
    } as Response)

    await expect(api('/explode')).rejects.toMatchObject({
      detail: 'Internal Server Error',
    })
  })

  it('calls onUnauthorized on 401', async () => {
    const onUnauthorized = vi.fn()
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'Token expired' }, 401))

    await expect(api('/me', { onUnauthorized })).rejects.toThrow(ApiError)
    expect(onUnauthorized).toHaveBeenCalledOnce()
  })

  it('skips onUnauthorized callback for non-401 errors', async () => {
    const onUnauthorized = vi.fn()
    fetchMock.mockResolvedValueOnce(jsonResponse({ detail: 'Forbidden' }, 403))

    await expect(api('/admin', { onUnauthorized })).rejects.toThrow(ApiError)
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('merges extra headers', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({}))

    await api('/wines', { headers: { 'X-Custom': 'yes' } as Record<string, string> })
    const headers = fetchMock.mock.calls[0][1].headers
    expect(headers['X-Custom']).toBe('yes')
    expect(headers['Content-Type']).toBe('application/json')
  })
})

describe('fetchAllPages', () => {
  it('fetches a single page when results < PAGE_SIZE', async () => {
    const items = Array.from({ length: 5 }, (_, i) => ({ id: i }))
    const client = vi.fn().mockResolvedValueOnce(items)

    const result = await fetchAllPages('/wines', client)
    expect(result).toEqual(items)
    expect(client).toHaveBeenCalledOnce()
    expect(client).toHaveBeenCalledWith(`/wines?limit=${API_PAGE_SIZE}&offset=0`)
  })

  it('fetches multiple pages until a short page', async () => {
    const page1 = Array.from({ length: API_PAGE_SIZE }, (_, i) => ({ id: i }))
    const page2 = [{ id: API_PAGE_SIZE }, { id: API_PAGE_SIZE + 1 }]
    const client = vi.fn().mockResolvedValueOnce(page1).mockResolvedValueOnce(page2)

    const result = await fetchAllPages('/wines', client)
    expect(result).toHaveLength(API_PAGE_SIZE + 2)
    expect(client).toHaveBeenCalledTimes(2)
    expect(client).toHaveBeenCalledWith(`/wines?limit=${API_PAGE_SIZE}&offset=0`)
    expect(client).toHaveBeenCalledWith(`/wines?limit=${API_PAGE_SIZE}&offset=${API_PAGE_SIZE}`)
  })

  it('returns empty array when first page is empty', async () => {
    const client = vi.fn().mockResolvedValueOnce([])

    const result = await fetchAllPages('/wines', client)
    expect(result).toEqual([])
    expect(client).toHaveBeenCalledOnce()
  })
})
