import { describe, expect, it } from 'vitest'

import { assignmentParams } from './assignment'

describe('assignmentParams', () => {
  it("bo'sh qiymatlar yuborilmaydi (o'zgartirmaslik)", () => {
    expect(assignmentParams({ departmentId: '', positionId: '', branchId: '' })).toEqual({})
  })
  it('"none" null ga, raqam songa aylanadi', () => {
    expect(assignmentParams({ departmentId: '3', positionId: 'none', branchId: '' })).toEqual({ department_id: 3, position_id: null })
  })
})
