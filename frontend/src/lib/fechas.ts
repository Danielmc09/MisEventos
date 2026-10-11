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
