import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Toast, type ToastProps } from "./Toast";

export type Aviso = Pick<ToastProps, "message" | "tone">;

const DURACION_MS = 4000;
const MAXIMO = 3;

interface AvisoVisible extends Aviso {
  id: number;
}

type Avisar = (aviso: Aviso) => void;

const Contexto = createContext<Avisar | null>(null);

/** Apila los avisos de toda la app: arriba a la derecha en escritorio, abajo al centro en móvil. */
export function ProveedorAvisos({ children }: { children: ReactNode }) {
  // El más nuevo primero.
  const [avisos, setAvisos] = useState<AvisoVisible[]>([]);
  const siguiente = useRef(0);
  const temporizadores = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const cerrar = useCallback((id: number) => {
    clearTimeout(temporizadores.current.get(id));
    temporizadores.current.delete(id);
    setAvisos((actuales) => actuales.filter((a) => a.id !== id));
  }, []);

  const avisar = useCallback<Avisar>(
    (aviso) => {
      const id = siguiente.current++;
      // El temporizador de uno que se va por el tope dispara igual y no encuentra nada que cerrar.
      setAvisos((actuales) => [{ ...aviso, id }, ...actuales].slice(0, MAXIMO));
      temporizadores.current.set(
        id,
        setTimeout(() => cerrar(id), DURACION_MS),
      );
    },
    [cerrar],
  );

  useEffect(() => {
    const activos = temporizadores.current;
    return () => activos.forEach(clearTimeout);
  }, []);

  return (
    <Contexto.Provider value={avisar}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-30 flex flex-col gap-2 md:inset-x-auto md:top-4 md:right-4 md:bottom-auto md:w-96">
        {avisos.map(({ id, ...aviso }) => (
          <Toast key={id} {...aviso} onClose={() => cerrar(id)} />
        ))}
      </div>
    </Contexto.Provider>
  );
}

/** Devuelve la función que muestra un aviso en el contenedor global. */
export function useAvisos(): Avisar {
  const avisar = useContext(Contexto);
  if (!avisar) throw new Error("useAvisos va dentro de ProveedorAvisos");
  return avisar;
}
