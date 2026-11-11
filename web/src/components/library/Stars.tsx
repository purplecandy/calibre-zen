import { IconStarFilled, IconStarHalfFilled } from '@tabler/icons-react'
import { cn } from '@/lib/utils'

/**
 * calibre keeps ratings out of 10, a star being 2. Drawn as the desktop's
 * rating widget draws them: five stars in the text colour, the empty ones
 * faded rather than given a colour of their own.
 */
export function Stars({
  rating,
  className,
}: {
  rating: number | undefined
  className?: string
}) {
  if (!rating) return null
  return (
    <span
      className={cn('inline-flex items-center gap-px', className)}
      role="img"
      aria-label={`${rating / 2} out of 5 stars`}
    >
      {Array.from({ length: 5 }, (_, i) => {
        const value = rating - i * 2
        const Icon = value === 1 ? IconStarHalfFilled : IconStarFilled
        return (
          <Icon
            key={i}
            className={cn('size-3.5', value <= 0 && 'opacity-25')}
          />
        )
      })}
    </span>
  )
}
