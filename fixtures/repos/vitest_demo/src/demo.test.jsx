import { AssertionError } from 'node:assert'
import { render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'
import { boom, boomLater } from './boom.js'
import List from './List.jsx'
import { sum } from './sum.js'

test('adds', () => { expect(sum(1, 2)).toBe(3) })
describe('group', () => { test('nested name', () => { expect(sum(2, 2)).toBe(4) }) })
test('renders', () => { render(<List items={['a']} />); expect(screen.queryByText('a')).not.toBeNull() })
test('fails by assertion', () => { expect(sum(1, 1)).toBe(3) })
test('fails in code', () => { expect(boom()).toBe(1) })
test('element not found', () => { render(<List items={[]} />); screen.getByText('nope') })
test('message names a path', () => { expect('/workspace/src/sum.js:1').toBe('elsewhere') })
test('caught with its cause', () => {
  try { boom() } catch (e) { throw Object.assign(new AssertionError({ message: `boom() threw: ${e}` }), { cause: e }) }
})
test('message with a stack line', () => {
  throw new AssertionError({ message: 'not here\n    at /workspace/src/sum.js:1:1' })
})
test('awaits code that fails', async () => { expect(await boomLater()).toBe(1) })
test.skip('skipped', () => {})
