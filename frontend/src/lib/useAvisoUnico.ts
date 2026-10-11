import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/** Lee el `aviso` que viaja en `history.state`, lo limpia de la ubicación y lo devuelve una sola vez. */
export function useAvisoUnico() {
  const { pathname, search, state } = useLocation();
  const navigate = useNavigate();
  const [aviso, setAviso] = useState<string | undefined>(
    (state as { aviso?: string } | null)?.aviso,
  );
  useEffect(() => {
    if (state) navigate(pathname + search, { replace: true, state: null });
  }, [state, pathname, search, navigate]);
  return [aviso, () => setAviso(undefined)] as const;
}
