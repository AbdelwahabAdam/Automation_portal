// Which version of the portal is running, under the الإدارة pages. Staff never see it; it is here
// so a problem can be reported against a known version, and so a deploy can be confirmed to have landed.
import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function Version() {
  const [running, setRunning] = useState(null);

  useEffect(() => {
    api('/admin/version').then(setRunning).catch(() => {});
  }, []);

  if (!running) return null;
  const parts = [
    `النسخة ${running.version}`,
    running.build && running.build !== '0' ? `بناء ${running.build}` : '',
    running.commit,
    running.built_at,
  ].filter(Boolean);
  return <p className="fl-version" data-fl-num><bdi>{parts.join(' · ')}</bdi></p>;
}
