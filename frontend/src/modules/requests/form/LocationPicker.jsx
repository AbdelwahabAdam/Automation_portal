// Picking the customer's place on a map (field type "location").
//
// The pin is the single source of truth: its position writes both the link and الإحداثيات, so the
// two can never describe different places. A Google share link carries a place name and no
// coordinates at all, which is why they used to be typed in by hand and drift apart.
import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Button, TextInput } from '../ds/index.jsx';
import { api } from '../api.js';

// Where the map opens when nothing is picked yet: the country, not a city, so no emirate is favoured
const UAE_CENTRE = [24.2, 54.6];
const UAE_ZOOM = 7;
const PICKED_ZOOM = 16;

// The link written from a pin. It holds the coordinates themselves, so anything reading the link
// later (Daftra, the work order, a phone opening it) lands exactly where the pin is.
export const linkFor = (lat, lng) => `https://www.google.com/maps?q=${lat.toFixed(6)},${lng.toFixed(6)}`;
export const coordinatesFor = (lat, lng) => `${lat.toFixed(6)}, ${lng.toFixed(6)}`;

// A point out of whatever is already saved: the coordinates first, else a link that carries some
const POINT = /(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)/;
export function pointOf(coordinates, link) {
  const found = String(coordinates || '').match(POINT) || String(link || '').match(POINT);
  if (!found) return null;
  const [lat, lng] = [Number(found[1]), Number(found[2])];
  return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180
    ? [lat, lng] : null;
}

// A pin drawn by the page itself: Leaflet's own marker images do not survive the build
const PIN = L.divIcon({ className: 'fl-map__pin', iconSize: [26, 26], iconAnchor: [13, 26] });

export default function LocationPicker({ spec, value, coordinates, invalid, onPick }) {
  const holder = useRef(null);
  const map = useRef(null);
  const marker = useRef(null);
  // The box holds the location itself: the link the person pasted stays in it, and a point taken
  // from the map puts its own link there. It is only a search box while something else is typed.
  const [query, setQuery] = useState(value || '');
  const [searching, setSearching] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => { if (value && value !== query) setQuery(value); }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  // Puts the pin somewhere. write: also tells the form, which is the only way these values are set
  // by the map. Showing where a point already is — one the client's address holds, or one typed
  // into الإحداثيات by hand — only moves the pin: rewriting the link there would take the field
  // the person is still typing in and lock it again.
  const place = useRef(() => {});
  place.current = (lat, lng, move = true, write = true) => {
    if (!map.current) return;
    if (marker.current) marker.current.setLatLng([lat, lng]);
    else {
      marker.current = L.marker([lat, lng], { icon: PIN, draggable: true }).addTo(map.current);
      marker.current.on('dragend', () => {
        const at = marker.current.getLatLng();
        place.current(at.lat, at.lng, false);
      });
    }
    if (move) map.current.setView([lat, lng], Math.max(map.current.getZoom(), PICKED_ZOOM));
    if (write) onPick(linkFor(lat, lng), coordinatesFor(lat, lng));
  };

  useEffect(() => {
    if (map.current || !holder.current) return;
    const at = pointOf(coordinates, value);
    map.current = L.map(holder.current, { attributionControl: true })
      .setView(at || UAE_CENTRE, at ? PICKED_ZOOM : UAE_ZOOM);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '© OpenStreetMap',
    }).addTo(map.current);
    map.current.on('click', (event) => place.current(event.latlng.lat, event.latlng.lng, false));
    if (at) place.current(at[0], at[1], true, false);
    // The map is often built while its box is still being laid out, and then draws at the wrong size
    setTimeout(() => map.current?.invalidateSize(), 60);
    return () => { map.current?.remove(); map.current = null; marker.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // A location filled in from elsewhere (the client's saved address) moves the pin to it
  useEffect(() => {
    const at = pointOf(coordinates, value);
    if (!at || !map.current) return;
    const now = marker.current?.getLatLng();
    if (now && Math.abs(now.lat - at[0]) < 1e-6 && Math.abs(now.lng - at[1]) < 1e-6) return;
    place.current(at[0], at[1], true, false);
  }, [value, coordinates]);

  async function search(event) {
    event?.preventDefault();
    const text = query.trim();
    if (!text) return;
    setSearching(true);
    setMessage('');
    // A pasted map link: a short one says nothing until it is followed, which only the server can do
    if (/^https?:\/\//i.test(text)) {
      try {
        const at = await api(`/location/from-link?url=${encodeURIComponent(text)}`);
        // The link kept on the request is the one the person pasted, not one written from the pin:
        // it is what they chose, and what anyone opening the request will recognise
        place.current(at.lat, at.lng, true, false);
        onPick(text, coordinatesFor(at.lat, at.lng));
      } catch (err) {
        // The link is kept even so — it is the customer's own, and the work order prints it —
        // and الإحداثيات unlock below for it to be filled in by hand
        onPick(text, '');
        setMessage(err.message || 'تعذّر قراءة الرابط. اكتب الإحداثيات أو اختر الموقع على الخريطة.');
      } finally {
        setSearching(false);
      }
      return;
    }
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=ae&q=${encodeURIComponent(text)}`;
      const found = await fetch(url, { headers: { Accept: 'application/json' } }).then((r) => r.json());
      if (!found.length) setMessage('لا يوجد مكان بهذا الاسم. حرّك الخريطة واضغط على الموقع.');
      else place.current(Number(found[0].lat), Number(found[0].lon));
    } catch {
      setMessage('تعذّر البحث. حرّك الخريطة واضغط على الموقع.');
    } finally {
      setSearching(false);
    }
  }

  function here() {
    // Browsers only give the location to a secure page; the portal is served over plain http
    if (!navigator.geolocation || !window.isSecureContext) {
      setMessage('تحديد موقعك الحالي يحتاج اتصالًا آمنًا (https). اضغط على الموقع في الخريطة.');
      return;
    }
    setMessage('جارٍ تحديد موقعك…');
    navigator.geolocation.getCurrentPosition(
      (position) => { setMessage(''); place.current(position.coords.latitude, position.coords.longitude); },
      () => setMessage('تعذّر تحديد موقعك. اضغط على الموقع في الخريطة.'),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  return (
    <div className="fl-map">
      <div className="fl-map__tools">
        <TextInput
          id={spec.name} value={query} placeholder="ابحث عن مكان، أو الصق رابط خرائط Google" icon="search" onIconClick={search}
          iconLabel="ابحث عن المكان" enterKeyHint="search" autoComplete="off"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') search(e); }}
        />
        <Button type="button" variant="secondary" icon="map-pin" loading={searching} onClick={here}>موقعي</Button>
      </div>
      <div ref={holder} className={`fl-map__canvas${invalid ? ' fl-map__canvas--invalid' : ''}`} />
      <div className="fl-map__foot">
        {coordinates
          ? <span className="fl-map__at">الموقع المختار: <bdi dir="ltr" data-fl-num>{coordinates}</bdi></span>
          : <span className="fl-map__at fl-map__at--empty">اضغط على موقع العميل في الخريطة</span>}
        {message && <span className="fl-map__says">{message}</span>}
      </div>
    </div>
  );
}
