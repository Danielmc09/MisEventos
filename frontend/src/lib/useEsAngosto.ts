import { useSyncExternalStore } from "react";

const CONSULTA = "(max-width: 767px)";

const existe = () => typeof window !== "undefined" && typeof window.matchMedia === "function";

function suscribir(avisar: () => void) {
  if (!existe()) return () => {};
  const mql = window.matchMedia(CONSULTA);
  mql.addEventListener("change", avisar);
  return () => mql.removeEventListener("change", avisar);
}

/** `true` por debajo del punto `md` de Tailwind (768 px). Sin `matchMedia` cuenta como escritorio. */
export function useEsAngosto(): boolean {
  return useSyncExternalStore(
    suscribir,
    () => existe() && window.matchMedia(CONSULTA).matches,
    () => false,
  );
}
