import { useId } from "react";
import styles from "../styles/VyasLogo.module.css";

const paths = [
  {
    key: "path-outer-left",
    className: styles.outerLeft,
    d: "M21.61 46.01L109.61 198.01L130.39 185.99L42.39 33.99Z",
  },
  {
    key: "path-outer-right",
    className: styles.outerRight,
    d: "M197.61 33.99L109.61 185.99L130.39 198.01L218.39 46.01Z",
  },
  {
    key: "path-inner-left",
    className: styles.innerLeft,
    d: "M80.73 76.21L112.73 131.48L127.27 123.06L95.27 67.79Z",
  },
  {
    key: "path-inner-right",
    className: styles.innerRight,
    d: "M144.73 67.79L112.73 123.06L127.27 131.48L159.27 76.21Z",
  },
  {
    key: "path-crown",
    className: styles.crown,
    d: "M120 16L152 64L136 64L120 40L104 64L88 64Z",
  },
  {
    key: "path-diamond",
    className: styles.diamond,
    d: "M120 98.8L133.2 112L120 125.2L106.8 112Z",
  },
];

export default function VyasLogo({
  variant = "gold",
  size = 40,
  animate = false,
  className = "",
}) {
  const rawId = useId().replace(/:/g, "");
  const goldId = `vyasGold-${rawId}`;
  const blueId = `vyasBlue-${rawId}`;
  const glowId = `vyasGlow-${rawId}`;
  const fill = variant === "blue" ? `url(#${blueId})` : `url(#${goldId})`;

  return (
    <svg
      className={[
        styles.logo,
        animate ? styles.animate : "",
        className,
      ].filter(Boolean).join(" ")}
      width={size}
      height={Math.round(size * 224 / 240)}
      viewBox="0 0 240 224"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
      style={{ "--vyas-logo-size": `${size}px` }}
    >
      <defs>
        <linearGradient id={goldId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f0c060" />
          <stop offset="40%" stopColor="#d4a843" />
          <stop offset="100%" stopColor="#8a6020" />
        </linearGradient>
        <linearGradient id={blueId} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#93c5fd" />
          <stop offset="48%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#1e40af" />
        </linearGradient>
        <filter id={glowId} x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#d4a843" floodOpacity="0.35" />
          <feDropShadow dx="0" dy="6" stdDeviation="8" floodColor="#8a6020" floodOpacity="0.18" />
        </filter>
      </defs>

      <g filter={variant === "gold" ? `url(#${glowId})` : undefined}>
        {paths.map((path) => (
          <path
            key={path.key}
            id={path.key}
            className={`${styles.logoPath} ${path.className}`}
            d={path.d}
            fill={fill}
            stroke={fill}
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        ))}
      </g>
    </svg>
  );
}
