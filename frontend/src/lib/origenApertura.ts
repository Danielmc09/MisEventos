/** El último elemento sobre el que se hizo click (con mouse, toque o teclado). */
let ultimoClick: Element | null = null;

if (typeof document !== "undefined") {
  document.addEventListener(
    "click",
    (e) => {
      if (!(e.target instanceof Element)) return;
      const clicado = e.target.closest("button, a") ?? e.target;
      // Una opción de menú desaparece al elegirla: el origen es el botón que abrió el menú.
      const menu = clicado.closest('[role="menu"]');
      const abrio = menu?.id ? document.querySelector(`[aria-controls="${menu.id}"]`) : null;
      ultimoClick = abrio ?? clicado;
    },
    true,
  );
}

/** El punto del panel desde el que crece al abrirse: el centro del elemento que lo abrió. */
export function origenDeApertura(panel: HTMLElement): string {
  if (!ultimoClick?.isConnected) return "center";
  const abre = ultimoClick.getBoundingClientRect();
  const caja = panel.getBoundingClientRect();
  const x = abre.left + abre.width / 2 - caja.left;
  const y = abre.top + abre.height / 2 - caja.top;
  return `${x}px ${y}px`;
}
