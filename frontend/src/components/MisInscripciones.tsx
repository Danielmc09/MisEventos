import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { components } from "../api/schema";
import { EventoCard } from "./EventoCard";
import { SesionesReservadas } from "./SesionesReservadas";
import { AlertaError } from "./ui/AlertaError";
import { Paginacion } from "./ui/Paginacion";
import { Pestanas } from "./ui/Pestanas";
import { Spinner } from "./ui/Spinner";
import { TextoSecundario } from "./ui/TextoSecundario";
import { TituloSeccion } from "./ui/TituloSeccion";

type Pagina = components["schemas"]["Pagina_InscripcionMia_"];

const PESTANAS = [
  {
    id: "proximos",
    titulo: "Próximos",
    filtros: "status=ACTIVE&when=upcoming",
    vacio: "No tenés inscripciones próximas",
  },
  {
    id: "pasados",
    titulo: "Pasados",
    filtros: "status=ACTIVE&when=past",
    vacio: "No tenés inscripciones pasadas",
  },
  // Las canceladas usan el `when` por defecto de la API (próximas).
  {
    id: "cancelados",
    titulo: "Cancelados",
    filtros: "status=CANCELLED",
    vacio: "No tenés inscripciones canceladas",
  },
] as const;

interface Resultado {
  consulta: string;
  pagina?: Pagina;
  error?: string;
}

export function MisInscripciones() {
  const [activa, setActiva] = useState<string>(PESTANAS[0].id);
  const [numero, setNumero] = useState(1);
  const [resultado, setResultado] = useState<Resultado | null>(null);

  const pestana = PESTANAS.find((p) => p.id === activa)!;
  const consulta = `${pestana.filtros}&page=${numero}`;

  useEffect(() => {
    let vigente = true;
    api<Pagina>(`/me/registrations?${consulta}`).then(
      (pagina) => vigente && setResultado({ consulta, pagina }),
      (e) =>
        vigente &&
        setResultado({
          consulta,
          error: e instanceof ApiError ? e.title : "Ocurrió un error inesperado",
        }),
    );
    return () => {
      vigente = false;
    };
  }, [consulta]);

  const actual = resultado?.consulta === consulta ? resultado : null;

  function cambiar(id: string) {
    setActiva(id);
    setNumero(1);
  }

  return (
    <section aria-labelledby="titulo-inscripciones" className="mt-8 flex flex-col gap-4">
      <TituloSeccion id="titulo-inscripciones">Mis inscripciones</TituloSeccion>
      <Pestanas
        etiqueta="Mis inscripciones"
        pestanas={PESTANAS.map(({ id, titulo }) => ({ id, titulo }))}
        activa={activa}
        onCambiar={cambiar}
      >
        {!actual && (
          <div className="flex justify-center p-10">
            <Spinner />
          </div>
        )}
        {actual?.error && <AlertaError title={actual.error} />}
        {actual?.pagina && actual.pagina.items.length === 0 && (
          <TextoSecundario>{pestana.vacio}</TextoSecundario>
        )}
        {actual?.pagina && actual.pagina.items.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {actual.pagina.items.map((i) => (
              <div key={i.id} className="flex flex-col gap-2">
                <EventoCard evento={i.event} />
                {activa === "proximos" && (
                  <SesionesReservadas evento={i.event.name} sesiones={i.reserved_sessions} />
                )}
              </div>
            ))}
          </div>
        )}
        {actual?.pagina && (
          <Paginacion
            pagina={actual.pagina.page}
            paginas={actual.pagina.pages}
            onCambiar={setNumero}
          />
        )}
      </Pestanas>
    </section>
  );
}
