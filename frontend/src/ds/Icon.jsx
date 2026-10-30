// Icon set of the Future Life design system (Design/portal/fl-core.js, FL.ICONS): 24px grid, stroked paths.
const ICONS = {
  check: ['M5 12.5l4.5 4.5L19 7.5'], x: ['M6 6l12 12', 'M18 6L6 18'], plus: ['M12 5v14', 'M5 12h14'], minus: ['M5 12h14'],
  'chevron-down': ['M6 9l6 6 6-6'], 'chevron-up': ['M6 15l6-6 6 6'], 'chevron-end': ['M9 6l6 6-6 6'], 'chevron-start': ['M15 6l-6 6 6 6'],
  'arrow-end': ['M5 12h14', 'M13 6l6 6-6 6'], 'arrow-start': ['M19 12H5', 'M11 6l-6 6 6 6'], search: ['M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14z', 'M20 20l-4-4'],
  eye: ['M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z', 'M12 9.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z'],
  'eye-off': ['M4 4l16 16', 'M9.9 5.8A9.7 9.7 0 0 1 12 5.5C18 5.5 21.5 12 21.5 12a17 17 0 0 1-3 3.7', 'M6.4 7.4C3.9 9.2 2.5 12 2.5 12S6 18.5 12 18.5c1.5 0 2.9-.4 4.1-1'],
  calendar: ['M4 6.5h16V20H4z', 'M4 10.5h16', 'M8 3.5v4', 'M16 3.5v4'], upload: ['M12 16V4', 'M7 9l5-5 5 5', 'M4 16v4h16v-4'], download: ['M12 4v12', 'M7 11l5 5 5-5', 'M4 16v4h16v-4'],
  file: ['M6 3h8l5 5v13H6z', 'M14 3v5h5'], 'file-text': ['M6 3h8l5 5v13H6z', 'M14 3v5h5', 'M9 13h7', 'M9 17h5'], image: ['M4 5h16v14H4z', 'M4 16l5-5 4 4 2-2 5 5', 'M15 9.5h.01'],
  copy: ['M9 9h11v11H9z', 'M5 15V4h11'], trash: ['M4 7h16', 'M10 11v6', 'M14 11v6', 'M6 7l1 13h10l1-13', 'M9 7V4h6v3'], edit: ['M4 20h4L19 9l-4-4L4 16z', 'M13.5 6.5l4 4'],
  more: ['M5 12h.01', 'M12 12h.01', 'M19 12h.01'], filter: ['M4 5h16l-6 7.5V19l-4-2v-4.5z'], sort: ['M8 4v16', 'M4 8l4-4 4 4', 'M16 20V4', 'M12 16l4 4 4-4'],
  info: ['M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z', 'M12 11v6', 'M12 7.5h.01'], 'alert-triangle': ['M12 3.5L2.5 20h19z', 'M12 10v4.5', 'M12 17.5h.01'],
  'alert-circle': ['M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z', 'M12 7.5v5.5', 'M12 16.5h.01'], 'check-circle': ['M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z', 'M8 12.5l3 3 5-6'],
  'x-circle': ['M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z', 'M9 9l6 6', 'M15 9l-6 6'], clock: ['M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z', 'M12 7v5l3 2'],
  refresh: ['M20 11a8 8 0 0 0-14.6-4.5L4 8', 'M4 4v4h4', 'M4 13a8 8 0 0 0 14.6 4.5L20 16', 'M20 20v-4h-4'], lock: ['M6 11h12v9H6z', 'M8.5 11V8a3.5 3.5 0 0 1 7 0v3'],
  user: ['M12 4a4 4 0 1 1 0 8 4 4 0 0 1 0-8z', 'M4.5 20c.8-3.5 3.8-5.5 7.5-5.5s6.7 2 7.5 5.5'],
  users: ['M9 5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7z', 'M2.5 19.5c.7-3 3.2-4.8 6.5-4.8s5.8 1.8 6.5 4.8', 'M16 5.3a3.5 3.5 0 0 1 0 6.4', 'M18 14.9c1.7.7 3 2.3 3.5 4.6'],
  phone: ['M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1.5 1.5 0 0 1-1.6 1.5A16 16 0 0 1 3.5 5.6 1.5 1.5 0 0 1 5 4z'],
  'map-pin': ['M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z', 'M12 7.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z'],
  link: ['M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1', 'M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1'], menu: ['M4 7h16', 'M4 12h16', 'M4 17h16'],
  grid: ['M4 4h7v7H4z', 'M13 4h7v7h-7z', 'M4 13h7v7H4z', 'M13 13h7v7h-7z'], list: ['M9 6h11', 'M9 12h11', 'M9 18h11', 'M4.5 6h.01', 'M4.5 12h.01', 'M4.5 18h.01'],
  inbox: ['M4 13l2.5-8h11L20 13v6H4z', 'M4 13h4.5l1.5 2.5h4l1.5-2.5H20'],
  settings: ['M12 9a3 3 0 1 1 0 6 3 3 0 0 1 0-6z', 'M12 2.5v3', 'M12 18.5v3', 'M2.5 12h3', 'M18.5 12h3', 'M5.3 5.3l2.1 2.1', 'M16.6 16.6l2.1 2.1', 'M5.3 18.7l2.1-2.1', 'M16.6 7.4l2.1-2.1'],
  'log-out': ['M10 4H5v16h5', 'M15 8l4 4-4 4', 'M19 12H9'], help: ['M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z', 'M9.5 9.5a2.5 2.5 0 0 1 4.8.9c0 1.7-2.3 2.1-2.3 3.6', 'M12 17h.01'],
  droplet: ['M12 3.5s6 6.5 6 10.5a6 6 0 0 1-12 0c0-4 6-10.5 6-10.5z'], tool: ['M14.5 6.5a4 4 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3l7.5-7.5', 'M14.5 6.5l3-3'],
  package: ['M4 7.5L12 3.5l8 4v9l-8 4-8-4z', 'M4 7.5l8 4 8-4', 'M12 11.5v9'], receipt: ['M6 3h12v18l-3-2-3 2-3-2-3 2z', 'M9 8h6', 'M9 12h6'],
  message: ['M4 5h16v11H9l-5 4z'], send: ['M4 12l16-8-6 16-3-6.5z', 'M11 13.5L20 4'], history: ['M4 12a8 8 0 1 0 2.4-5.7L4 8.5', 'M4 4v4.5h4.5', 'M12 8v4l3 2'],
  external: ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v6H4V6h6'], sliders: ['M4 7h10', 'M18 7h2', 'M4 17h4', 'M12 17h8', 'M14 5v4', 'M8 15v4'],
  shield: ['M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z'], 'minus-circle': ['M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z', 'M8 12h8'],
  loader: ['M12 3a9 9 0 1 0 9 9'], dot: ['M12 10a2 2 0 1 1 0 4 2 2 0 0 1 0-4z'], layers: ['M12 3.5l8.5 4.5L12 12.5 3.5 8z', 'M3.5 12.5L12 17l8.5-4.5', 'M3.5 16.5L12 21l8.5-4.5'],
  mail: ['M4 6h16v12H4z', 'M4 7l8 6 8-6'],
  // Not in FL.ICONS yet: the portal shares a document with whatever app the device offers
  share: ['M18 3a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z', 'M6 9.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z',
          'M18 16a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z', 'M8.2 10.9l7.6-4.3', 'M8.2 13.1l7.6 4.3'],
};

// Directional icons point the other way in right-to-left text
const FLIP = new Set(['chevron-end', 'chevron-start', 'arrow-end', 'arrow-start', 'log-out', 'send', 'external']);

export default function Icon({ name, size = 20, label, className }) {
  const paths = ICONS[name] || ICONS.dot;
  const classes = ['fl-icon', FLIP.has(name) && 'fl-icon--flip', name === 'loader' && 'fl-icon--spin', className].filter(Boolean).join(' ');
  return (
    <svg
      className={classes} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" focusable="false"
      aria-hidden={label ? undefined : 'true'} role={label ? 'img' : undefined} aria-label={label}
    >
      {paths.map((d) => <path key={d} d={d} />)}
    </svg>
  );
}
