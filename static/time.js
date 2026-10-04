// Display-only time helpers. Stored/API timestamps remain ISO/UTC.
(function (root) {
  function formatKST(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Seoul',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false,
    }).formatToParts(date).reduce((out, part) => {
      out[part.type] = part.value;
      return out;
    }, {});
    return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second} KST`;
  }

  function localDateString(date = new Date()) {
    const pad = value => String(value).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  root.formatKST = formatKST;
  root.localDateString = localDateString;
  if (typeof module !== 'undefined') module.exports = { formatKST, localDateString };
})(typeof globalThis !== 'undefined' ? globalThis : window);
