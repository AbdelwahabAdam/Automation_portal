import { useEffect, useState } from 'react';

// Runs a screen's requests one at a time and keeps what to show about them:
// busy (the name of the one running, '' when none), error (the last failure) and ok (a success message).
// run() resolves to true when the action succeeded.
export function useAction() {
  const [state, setState] = useState({ busy: '', error: '', ok: '' });

  async function run(name, action, ok = '') {
    setState({ busy: name, error: '', ok: '' });
    try {
      await action();
      setState({ busy: '', error: '', ok });
      return true;
    } catch (err) {
      setState({ busy: '', error: err.message, ok: '' });
      return false;
    }
  }

  const clear = () => setState((current) => ({ ...current, error: '', ok: '' }));
  return { ...state, run, clear };
}

// The on-screen keyboard covers the bottom of a phone. While it is open, the bottom bar and the
// sticky action bar must not sit on top of it; they go back to where they were when it closes.
// The keyboard has no event of its own: it is known by how much it shrinks the visible area.
const KEYBOARD_MIN_HEIGHT = 140;

export function useKeyboardOpen() {
  useEffect(() => {
    const viewport = window.visualViewport;
    // Only a touch screen has one; a mouse pointer never opens a keyboard over the page
    if (!viewport || !window.matchMedia('(pointer: coarse)').matches) return undefined;

    const update = () => {
      const covered = window.innerHeight - viewport.height - viewport.offsetTop;
      document.body.classList.toggle('fl-keyboard', covered > KEYBOARD_MIN_HEIGHT);
    };
    update();
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    return () => {
      viewport.removeEventListener('resize', update);
      viewport.removeEventListener('scroll', update);
      document.body.classList.remove('fl-keyboard');
    };
  }, []);
}
