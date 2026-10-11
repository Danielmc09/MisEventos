interface Router {
  navigate: (to: string) => void;
  actual: string;
}

let router: Router | null = null;

/** App registra acá el router, para que el cliente HTTP pueda navegar sin ser un componente. */
export function registrarRouter(nuevo: Router) {
  router = nuevo;
}

export function irALogin() {
  if (!router || /^\/(login|registro)(\/|\?|$)/.test(router.actual)) return;
  router.navigate(`/login?next=${encodeURIComponent(router.actual)}`);
}
