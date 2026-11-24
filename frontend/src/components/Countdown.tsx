import { useEffect, useState } from 'react';
import { formatCountdown } from '../lib/contestRoom';

/** Ticks on its own so only this text re-renders every second. */
export function Countdown({ target, onElapsed }: { target: string; onElapsed?: () => void }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);
  const elapsed = now >= Date.parse(target);
  useEffect(() => { if (elapsed) onElapsed?.(); }, [elapsed, onElapsed]);
  return <span className="tabular-nums">{formatCountdown(target, now)}</span>;
}
