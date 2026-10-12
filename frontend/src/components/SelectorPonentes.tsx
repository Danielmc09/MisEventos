import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { errorDeFormulario } from "../lib/errores";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";

export type PonenteDeSesion = components["schemas"]["PonenteDeSesion"];
type PaginaPonentes = components["schemas"]["Pagina_PonenteSalida_"];

const ESPERA_MS = 300;

interface Props {
  seleccionados: PonenteDeSesion[];
  onChange: (ponentes: PonenteDeSesion[]) => void;
  /** Error de la API sobre la lista de ponentes (ids borrados, máximo superado). */
  error?: string;
}

export function SelectorPonentes({ seleccionados, onChange, error }: Props) {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState<PonenteDeSesion[]>([]);
  const consulta = texto.trim();
  const [creando, setCreando] = useState(false);
  const [nombre, setNombre] = useState("");
  const [errorNombre, setErrorNombre] = useState<string>();
  const [guardando, setGuardando] = useState(false);

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

  async function crear() {
    setGuardando(true);
    setErrorNombre(undefined);
    try {
      const nuevo = await api<PonenteDeSesion>("/speakers", {
        method: "POST",
        body: JSON.stringify({ full_name: nombre.trim() }),
      });
      onChange([...seleccionados, nuevo]);
      setCreando(false);
      setNombre("");
    } catch (e) {
      const { campos, general } = errorDeFormulario(e);
      setErrorNombre(campos.full_name ?? general ?? undefined);
    } finally {
      setGuardando(false);
    }
  }

  const elegidos = new Set(seleccionados.map((p) => p.id));
  const visibles = consulta ? resultados.filter((p) => !elegidos.has(p.id)) : [];

  return (
    <div className="flex flex-col gap-2">
      <Input
        label="Buscar ponente"
        error={error}
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
      {creando ? (
        <div className="flex flex-col gap-2">
          <Input
            label="Nombre del ponente"
            value={nombre}
            error={errorNombre}
            onChange={(e) => setNombre(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              e.preventDefault();
              void crear();
            }}
          />
          <div className="flex gap-3">
            <Button type="button" loading={guardando} onClick={crear}>
              Guardar ponente
            </Button>
            <button type="button" onClick={() => setCreando(false)}>
              Cancelar ponente
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setCreando(true)}
          className="self-start rounded-md border border-gray-300 px-3 py-1"
        >
          Crear ponente nuevo
        </button>
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
