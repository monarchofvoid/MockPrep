/**
 * MockBrowserSkeleton
 * Renders 6 placeholder MockCards that match the real MockCard layout
 * (examBadge + difficulty pill, title, year, 3-col meta boxes, start button).
 * Count of 6 fills a typical 3-col grid without visual emptiness.
 */

import s from "./Skeleton.module.css";

const Blk = ({ className, style }) => (
  <div className={`${s.block} ${className || ""}`} style={style} />
);

function SkeletonMockCard() {
  return (
    <div className={s.mockCard}>
      {/* Badge row */}
      <div className={s.mockCardHeader}>
        <Blk className={s.mockBadge} />
        <Blk className={s.mockDifficulty} />
      </div>

      {/* Subject title */}
      <Blk className={s.mockTitle} />

      {/* Year */}
      <Blk className={s.mockYear} />

      {/* Meta row: Questions / Duration / Marks */}
      <div className={s.mockMetaRow}>
        <Blk className={s.mockMetaBox} />
        <Blk className={s.mockMetaBox} />
        <Blk className={s.mockMetaBox} />
      </div>

      {/* Start button */}
      <Blk className={s.mockBtn} />
    </div>
  );
}

export default function MockBrowserSkeleton() {
  return (
    <div className={s.mockGrid}>
      {Array.from({ length: 6 }, (_, i) => (
        <SkeletonMockCard key={i} />
      ))}
    </div>
  );
}
