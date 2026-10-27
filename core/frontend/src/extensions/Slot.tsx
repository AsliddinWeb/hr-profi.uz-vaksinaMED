import { getSlot } from './registry'

export function Slot({ name }: { name: string }) {
  const items = getSlot(name)
  if (items.length === 0) return null
  return (
    <>
      {items.map((Item, i) => (
        <Item key={`${name}-${i}`} />
      ))}
    </>
  )
}
