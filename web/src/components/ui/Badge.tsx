import clsx from 'clsx'

type BadgeVariant = 'green' | 'gray' | 'yellow' | 'red' | 'blue' | 'purple'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
}

const variants: Record<BadgeVariant, string> = {
  green: 'bg-green-100 text-green-800',
  gray: 'bg-gray-100 text-gray-700',
  yellow: 'bg-yellow-100 text-yellow-800',
  red: 'bg-red-100 text-red-800',
  blue: 'bg-blue-100 text-blue-800',
  purple: 'bg-purple-100 text-purple-800',
}

export default function Badge({ children, variant = 'gray' }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        variants[variant],
      )}
    >
      {children}
    </span>
  )
}
