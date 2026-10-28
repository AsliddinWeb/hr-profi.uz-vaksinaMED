import { cn } from '../../lib/cn'

const DEFAULT_LOGO = '/logo.png'

/** Brend logotipi: standart logo uchun to'q mavzuda oq variant, mijoz logosi uchun oq fonli «plashka». */
export function BrandLogo({ src, alt, className }: { src?: string | null; alt: string; className?: string }) {
  const logo = src ?? DEFAULT_LOGO
  if (logo === DEFAULT_LOGO) {
    return (
      <>
        <img src={DEFAULT_LOGO} alt={alt} className={cn('object-contain dark:hidden', className)} />
        <img src="/logo-dark.png" alt={alt} className={cn('hidden object-contain dark:block', className)} />
      </>
    )
  }
  return <img src={logo} alt={alt} className={cn('object-contain dark:rounded-lg dark:bg-white dark:px-2 dark:py-1', className)} />
}
