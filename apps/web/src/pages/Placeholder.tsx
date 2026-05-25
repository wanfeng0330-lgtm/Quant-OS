import { ReactNode } from 'react'
import { Construction } from 'lucide-react'

interface PlaceholderProps {
  title: string
  description: string
  icon?: ReactNode
}

export default function Placeholder({ title, description, icon }: PlaceholderProps) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100 dark:bg-gray-800">
          {icon || <Construction className="h-8 w-8 text-gray-400" />}
        </div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
        <p className="mt-1 max-w-sm text-sm text-gray-500">{description}</p>
        <p className="mt-4 text-xs text-gray-400">Coming Soon</p>
      </div>
    </div>
  )
}
