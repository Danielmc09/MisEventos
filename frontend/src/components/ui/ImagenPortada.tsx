import portada480 from "../../assets/portada-480.webp";
import portada960 from "../../assets/portada-960.webp";
import portada1440 from "../../assets/portada-1440.webp";

/**
 * La ilustración de la cabecera del inicio. Es decorativa (`alt=""`), está arriba de todo
 * (carga con prioridad, sin `loading="lazy"`) y trae su tamaño para que la página no salte.
 */
export function ImagenPortada() {
  return (
    <img
      src={portada1440}
      srcSet={`${portada480} 480w, ${portada960} 960w, ${portada1440} 1440w`}
      sizes="(min-width: 72rem) 1152px, 100vw"
      width={1440}
      height={360}
      alt=""
      fetchPriority="high"
      className="h-auto w-full rounded-lg"
    />
  );
}
