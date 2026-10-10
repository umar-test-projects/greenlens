export const normalize = degrees => ((degrees % 360) + 360) % 360;
export function headingFromEvent(event) {
 if (Number.isFinite(event.webkitCompassHeading)) {
  if (event.webkitCompassAccuracy < 0) return null;
  return normalize(event.webkitCompassHeading);
 }
 return event.absolute === true && Number.isFinite(event.alpha) ? normalize(360-event.alpha) : null;
}
