import { Swords, Flame, Skull, Lock, Crosshair, Ban, Banknote, MapPinned } from 'lucide-react';

// Conflict type → Lucide icon component (SVG, not emoji)
const TYPE_ICON = {
  war: Swords,
  civil_war: Flame,
  genocide: Skull,
  occupation: Lock,
  proxy_war: Crosshair,
  sanctions: Ban,
  funding: Banknote,
  disputed_territory: MapPinned,
};

export function TypeIcon({ type, size = 16, ...props }) {
  const Ico = TYPE_ICON[type] || Swords;
  return <Ico size={size} strokeWidth={2} {...props} />;
}
