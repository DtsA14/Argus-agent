import { expect, test } from 'vitest'
import { sum } from './sum.js'

test('jsx', () => { expect(sum(1, 1)).toBe(2) })
