export function CardSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4 animate-pulse">
      <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded w-3/4 mb-3" />
      <div className="h-3 bg-gray-200 dark:bg-gray-800 rounded w-1/2 mb-2" />
      <div className="h-3 bg-gray-200 dark:bg-gray-800 rounded w-1/3" />
    </div>
  );
}

export function StatSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 p-4 animate-pulse">
      <div className="h-3 bg-gray-200 dark:bg-gray-800 rounded w-16 mb-3" />
      <div className="h-7 bg-gray-200 dark:bg-gray-800 rounded w-10" />
    </div>
  );
}

export function ListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {[...Array(count)].map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="h-8 bg-gray-200 dark:bg-gray-800 rounded w-48" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <StatSkeleton key={i} />)}
      </div>
      <ListSkeleton count={3} />
    </div>
  );
}