interface Props {
  status: 'healthy' | 'degraded' | 'offline';
}

export default function ConnectionStatus({ status }: Props) {
  const colors = {
    healthy: 'bg-green-500',
    degraded: 'bg-amber-500',
    offline: 'bg-red-500',
  };

  return (
    <div className="flex items-center gap-2">
      <span className={`w-3 h-3 rounded-full ${colors[status]}`} />
      <span className="text-sm capitalize text-gray-700">{status}</span>
    </div>
  );
}
