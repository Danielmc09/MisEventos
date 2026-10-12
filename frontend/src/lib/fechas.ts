const bogota = new Intl.DateTimeFormat("es-CO", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "America/Bogota",
});

/** Las fechas llegan en UTC; se muestran siempre en hora de Bogotá. */
export const formatearFecha = (iso: string) => bogota.format(new Date(iso));

// Colombia no tiene horario de verano: el desfase es siempre -05:00.
const DESFASE_BOGOTA_MS = 5 * 3600_000;

/** Del `datetime-local` (hora de Bogotá) al ISO 8601 que espera la API. */
export const aISOBogota = (local: string) => `${local}:00-05:00`;

/** Del ISO de la API al valor de un `datetime-local` en hora de Bogotá. */
export const aInputBogota = (iso: string) =>
  new Date(new Date(iso).getTime() - DESFASE_BOGOTA_MS).toISOString().slice(0, 16);

const diaBogotaFmt = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota" });
const etiquetaDiaFmt = new Intl.DateTimeFormat("es-CO", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "America/Bogota",
});
const horaFmt = new Intl.DateTimeFormat("es-CO", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "America/Bogota",
});

/** El día calendario en Bogotá (`2026-10-10`): sirve para agrupar y ordenar. */
export const diaBogota = (iso: string) => diaBogotaFmt.format(new Date(iso));

/** "Sábado, 10 de octubre de 2026", en hora de Bogotá. */
export const etiquetaDia = (iso: string) => {
  const texto = etiquetaDiaFmt.format(new Date(iso));
  return texto.charAt(0).toUpperCase() + texto.slice(1);
};

/** "20:30", en hora de Bogotá. */
export const horaBogota = (iso: string) => horaFmt.format(new Date(iso));
