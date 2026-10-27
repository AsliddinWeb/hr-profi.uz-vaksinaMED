import clsx, { type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** clsx + tailwind-merge: ziddiyatli sinflar (masalan `w-full` va `w-auto`) bo'lsa, oxirgisi g'olib bo'ladi. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
