import { describe, expect, it } from 'vitest'

import { extensionApi, getExtensionNavItems, getExtensionRoutes, getSlot } from './registry'

describe('extension registry', () => {
  it('route, nav va slot qo\'shadi', () => {
    const Comp = () => null
    extensionApi.addRoute({ path: '/x' })
    extensionApi.addNavItem({ id: 'x', label: { uz: 'X', ru: 'X' }, to: '/x' })
    extensionApi.slot('a', Comp)
    extensionApi.slot('a', Comp)

    expect(getExtensionRoutes()).toHaveLength(1)
    expect(getExtensionNavItems()[0].id).toBe('x')
    expect(getSlot('a')).toHaveLength(2)
    expect(getSlot('missing')).toEqual([])
  })
})
