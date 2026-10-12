import { EnlaceBoton } from "../../components/ui/EnlaceBoton";
import { Pagina, TituloPagina } from "../../components/ui/Pagina";

export default function NoEncontrada() {
  return (
    <Pagina>
      <TituloPagina>No encontramos esa página</TituloPagina>
      <div>
        <EnlaceBoton to="/">Volver al inicio</EnlaceBoton>
      </div>
    </Pagina>
  );
}
