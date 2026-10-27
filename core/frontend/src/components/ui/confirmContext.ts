import { createContext, useContext } from 'react'

export interface ConfirmOptions {
  title: string
  body?: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}

export type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>

export const ConfirmContext = createContext<ConfirmFn>(() => Promise.resolve(false))

/** `if (await confirm({ title, danger: true })) ...` */
export const useConfirm = () => useContext(ConfirmContext)
