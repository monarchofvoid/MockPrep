/**
 * HistorySkeleton
 * Used in AIMockGeneratorPage's right panel while AI mock history loads.
 * Renders 3 placeholder HistoryCard shapes.
 */

import s from "./Skeleton.module.css";

const Blk = ({ className, style }) => (
  <div className={`${s.block} ${className || ""}`} style={style} />
);

function SkeletonHistoryCard() {
  return (
    <div className={s.historyCard}>
      <div className={s.historyLeft}>
        <Blk className={s.historySubject} />
        <Blk className={s.historyMeta} />
      </div>
      <div className={s.historyRight}>
        <Blk className={s.historyScore} />
        <Blk className={s.historyBtn} />
      </div>
    </div>
  );
}

export default function HistorySkeleton() {
  return (
    <>
      {Array.from({ length: 3 }, (_, i) => (
        <SkeletonHistoryCard key={i} />
      ))}
    </>
  );
}
