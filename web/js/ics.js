// @ts-check
/**
 * Calendar export. Built in the browser, so the deadline never has to be
 * sent anywhere to become a reminder.
 */

/** Lines in an iCalendar file are separated by CRLF. */
const CRLF = '\r\n';

/** How many days before the date the alarm fires. */
export const ALARM_DAYS_BEFORE = 2;

/**
 * Escape a value for an iCalendar property.
 * @param {string} value
 * @returns {string}
 */
export function escapeText(value) {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n');
}

/**
 * Turn an ISO date into the YYYYMMDD form an all-day event uses.
 * @param {string} iso
 * @returns {string}
 */
export function compactDate(iso) {
  return iso.replace(/-/g, '');
}

/**
 * The day after a date, so an all-day event ends correctly.
 * @param {string} iso
 * @returns {string}
 */
export function nextDay(iso) {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

/**
 * Build an all-day VEVENT for the respond-by date, with an alarm.
 * @param {{date: string, title: string, description: string, stamp?: string}} event
 * @returns {string}
 */
export function buildCalendar(event) {
  const stamp = (event.stamp ?? new Date().toISOString()).replace(/[-:]/g, '').replace(/\.\d+/, '');
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Mohlat//Respond-by date//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:mohlat-${compactDate(event.date)}-${stamp}`,
    `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${compactDate(event.date)}`,
    `DTEND;VALUE=DATE:${compactDate(nextDay(event.date))}`,
    `SUMMARY:${escapeText(event.title)}`,
    `DESCRIPTION:${escapeText(event.description)}`,
    'BEGIN:VALARM',
    `TRIGGER:-P${ALARM_DAYS_BEFORE}D`,
    'ACTION:DISPLAY',
    `DESCRIPTION:${escapeText(event.title)}`,
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
  ];
  return lines.join(CRLF) + CRLF;
}

/**
 * Offer the calendar file to the browser as a download.
 * @param {string} calendar
 * @param {string} [filename]
 * @returns {void}
 */
export function downloadCalendar(calendar, filename = 'mohlat-deadline.ics') {
  const blob = new Blob([calendar], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
