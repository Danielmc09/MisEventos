import { FormularioEvento } from "../../components/FormularioEvento";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";
import { Tarjeta } from "../../components/ui/Tarjeta";
import { useTienePermiso } from "../../stores/session";

export default function EventoNuevo() {
  const puede = useTienePermiso("evento:crear");
  return (
    <Pagina>
      <TituloPagina>Nuevo evento</TituloPagina>
      {puede ? (
        <Tarjeta as="div">
          <FormularioEvento />
        </Tarjeta>
      ) : (
        <p>No tenés permiso para crear eventos</p>
      )}
    </Pagina>
  );
}
