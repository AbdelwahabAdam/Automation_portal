// Showing the files attached to a request: a small picture of an image, an icon for anything else.
// The files need the login header, so they are fetched rather than linked to.
import { useEffect, useState } from 'react';
import { attachmentUrl, openAttachment } from '../../api/http.js';
import { Icon } from '../../ds/index.jsx';

export const isImage = (file) => /^image\//.test(file.content_type || '');

export const fileSize = (bytes) => (bytes >= 1024 * 1024
  ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
  : `${Math.max(1, Math.round(bytes / 1024))} KB`);

// The picture itself once it has been fetched; an icon for a PDF, a video, or an image that fails
export function Thumb({ file }) {
  const [url, setUrl] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!isImage(file)) return undefined;
    let wanted = true;
    attachmentUrl(file.id).then((found) => wanted && setUrl(found)).catch(() => wanted && setFailed(true));
    return () => { wanted = false; };
  }, [file.id, file.content_type]);

  const icon = /pdf/.test(file.content_type) ? 'file-text' : /^video\//.test(file.content_type) ? 'image' : 'file';
  if (!isImage(file) || failed) return <span className="fl-thumb fl-thumb--icon"><Icon name={icon} size={18} /></span>;
  if (!url) return <span className="fl-thumb fl-thumb--loading" />;
  return <img className="fl-thumb" src={url} alt="" loading="lazy" />;
}

// One attached file: its picture, its name (opens it), and its size
export function FileRow({ file, children }) {
  return (
    <div className="fl-file">
      <button type="button" className="fl-file__open" onClick={() => openAttachment(file.id)} title={`فتح ${file.filename}`}>
        <Thumb file={file} />
      </button>
      <button type="button" className="fl-link fl-file__name" onClick={() => openAttachment(file.id)}><bdi>{file.filename}</bdi></button>
      <span className="fl-file__size" data-fl-num>{fileSize(file.size)}</span>
      {children}
    </div>
  );
}
