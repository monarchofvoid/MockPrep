import { useEffect, useState, useRef } from "react";
import styles from "../styles/Timer.module.css";

export default function Timer({ durationSeconds, onExpire }) {
  const [seconds, setSeconds] = useState(durationSeconds);
  const intervalRef = useRef(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setSeconds((s) => {
        if (s <= 1) {
          clearInterval(intervalRef.current);
          onExpire();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(intervalRef.current);
  }, [onExpire]);

  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  const display = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

  const cls =
    seconds < 120
      ? styles.critical
      : seconds < 300
      ? styles.warning
      : styles.normal;

  // Return seconds remaining (for the parent to compute time_taken)
  Timer.getSecondsLeft = () => seconds;

  return (
    <div className={`${styles.timer} ${cls}`} aria-live="polite" aria-label={`Time remaining: ${display}`}>
      {display}
    </div>
  );
}
