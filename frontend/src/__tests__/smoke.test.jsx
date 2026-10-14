import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react'
import App from '../App'

const errors = []
beforeEach(() => { cleanup(); errors.length = 0; vi.spyOn(console, 'error').mockImplementation((...a) => errors.push(a.join(' '))) })

async function visit(path, text) {
  window.history.pushState({}, '', path)
  render(<App />)
  await waitFor(() => expect(screen.getAllByText(text).length).toBeGreaterThan(0), { timeout: 15000 })
  const real = errors.filter((e) => !/not wrapped in act|ResizeObserver|width\(0\)|height\(0\)|Warning: An update/.test(e))
  expect(real).toEqual([])
}

describe('every page renders against the real backend', () => {
  it('dashboard shows real totals and charts', async () => {
    await visit('/', 'Total today')
    await waitFor(() => expect(document.querySelector('.recharts-responsive-container')).not.toBeNull(), { timeout: 15000 })
    expect(screen.getAllByText('Cars').length).toBeGreaterThan(0)
  })
  it('live monitoring', async () => { await visit('/live', 'Live monitoring'); await screen.findByText('Start processing') })
  it('cameras lists the seeded camera', async () => { await visit('/cameras', 'Demo Camera 1') })
  it('areas', async () => { await visit('/areas', 'Area A') })
  it('analytics incl. prediction panel', async () => { await visit('/analytics', 'Traffic analytics'); await screen.findByText(/Traffic prediction/) })
  it('history table loads events and supports search', async () => {
    await visit('/history', 'Historical data')
    await waitFor(() => expect(document.querySelectorAll('tbody tr').length).toBeGreaterThan(5), { timeout: 15000 })
    fireEvent.change(screen.getByPlaceholderText(/type, camera/), { target: { value: 'bus' } })
    await waitFor(() => { const rows = [...document.querySelectorAll('tbody tr')]; expect(rows.length).toBeGreaterThan(0); expect(rows.every((r) => /bus/i.test(r.textContent))).toBe(true) }, { timeout: 15000 })
  })
  it('reports', async () => { await visit('/reports', 'Total vehicles') })
  it('settings shows health', async () => { await visit('/settings', 'System health'); await screen.findByText('YOLO model') })
})
