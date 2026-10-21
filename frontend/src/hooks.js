import { useState } from 'react';

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
