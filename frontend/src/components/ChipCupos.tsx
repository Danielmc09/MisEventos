interface Props {
  capacidad: number;
  libres: number;
  unidad?: "cupo" | "lugar";
}

export function ChipCupos({ unidad }: Props) {
  return unidad === undefined ? null : null;
}
