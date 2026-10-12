import { Button } from "./Button";

export interface PaginacionProps {
  pagina: number;
  paginas: number;
  onCambiar: (pagina: number) => void;
}

export function Paginacion({ pagina, paginas, onCambiar }: PaginacionProps) {
  if (paginas <= 1) return null;
  return (
    <nav aria-label="Paginación" className="flex flex-wrap items-center justify-center gap-4">
      <Button variante="secundario" disabled={pagina <= 1} onClick={() => onCambiar(pagina - 1)}>
        Anterior
      </Button>
      <span>
        Página {pagina} de {paginas}
      </span>
      <Button
        variante="secundario"
        disabled={pagina >= paginas}
        onClick={() => onCambiar(pagina + 1)}
      >
        Siguiente
      </Button>
    </nav>
  );
}
