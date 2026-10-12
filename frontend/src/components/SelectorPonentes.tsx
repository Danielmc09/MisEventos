import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { Input } from "./ui/Input";

export type PonenteDeSesion = components["schemas"]["PonenteDeSesion"];
type PaginaPonentes = components["schemas"]["Pagina_PonenteSalida_"];

const ESPERA_MS = 300;

interface Props {
  seleccionados: PonenteDeSesion[];
  onChange: (ponentes: PonenteDeSesion[]) => void;
}

export function SelectorPonentes({ seleccionados, onChange }: Props) {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState<PonenteDeSesion[]>([]);
  const consulta = texto.trim();

  useEffect(() => {
    if (!consulta) return;
    let vigente = true;
    const espera = setTimeout(() => {
      api<PaginaPonentes>(`/speakers?q=${encodeURIComponent(consulta)}`).then(
        (pagina) => vigente && setResultados(pagina.items),
        () => vigente && setResultados([]),
      );
    }, ESPERA_MS);
    return () => {
      vigente = false;
      clearTimeout(espera);
    };
  }, [consulta]);

  const elegidos = new Set(seleccionados.map((p) => p.id));
  const visibles = consulta ? resultados.filter((p) => !elegidos.has(p.id)) : [];

  return (
    <div className="flex flex-col gap-2">
      <Input
        label="Buscar ponente"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && e.preventDefault()}
      />
      {visibles.length > 0 && (
        <ul aria-label="Resultados" className="flex flex-col gap-1">
          {visibles.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                aria-label={`Agregar a ${p.full_name}`}
                onClick={() => onChange([...seleccionados, p])}
                className="rounded-md border border-gray-300 px-3 py-1"
              >
                {p.full_name}
              </button>
            </li>
          ))}
        </ul>
      )}
      {seleccionados.length > 0 && (
        <ul aria-label="Ponentes elegidos" className="flex flex-wrap gap-2">
          {seleccionados.map((p) => (
            <li key={p.id} className="flex items-center gap-2 rounded-full bg-indigo-100 px-3 py-1">
              {p.full_name}
              <button
                type="button"
                aria-label={`Quitar a ${p.full_name}`}
                onClick={() => onChange(seleccionados.filter((q) => q.id !== p.id))}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
