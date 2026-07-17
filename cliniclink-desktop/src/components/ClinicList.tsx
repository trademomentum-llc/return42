import { useClinics } from '../hooks/useClinics';

interface Props {
  selected: string | null;
  onSelect: (nodeId: string) => void;
}

export default function ClinicList({ selected, onSelect }: Props) {
  const { data: clinics, isLoading } = useClinics();

  if (isLoading) return <p>Discovering clinics...</p>;
  if (!clinics?.length) return <p className="text-amber-600">No clinics discovered on mesh.</p>;

  return (
    <div className="space-y-2">
      {clinics.map((c) => (
        <button
          key={c.node_id}
          onClick={() => onSelect(c.node_id)}
          className={`w-full text-left p-3 rounded border ${
            selected === c.node_id ? 'border-blue-600 bg-blue-50' : 'border-gray-200'
          }`}
        >
          <span className="font-medium">{c.node_id}</span>
        </button>
      ))}
    </div>
  );
}
