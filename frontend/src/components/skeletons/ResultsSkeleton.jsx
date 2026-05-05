/**
 * ResultsSkeleton
 * Mirrors the ResultsPage structure:
 *   - Score hero (animated ring + breakdown + stats)
 *   - Tab strip placeholder
 *   - Topic cards grid (8 cards)
 *
 * The page header (back button, subject, attempt#) is NOT skeletonised
 * because attemptId is available from useParams immediately.
 */

import s from "./Skeleton.module.css";

const Blk = ({ className, style }) => (
  <div className={`${s.block} ${className || ""}`} style={style} />
);

function SkeletonScoreHero() {
  return (
    <div className={s.scoreHero}>
      {/* Score ring */}
      <Blk className={s.scoreCircle} />

      {/* Correct / Wrong / Skipped breakdown */}
      <div className={s.scoreBreakdownSkel}>
        {[0, 1, 2].map((i) => (
          <div key={i} className={s.scoreBreakItem}>
            <Blk className={s.scoreBreakVal} />
            <Blk className={s.scoreBreakLbl} />
          </div>
        ))}
      </div>

      {/* Stats: Raw score / Accuracy / Attempt rate / Time / Avg time */}
      <div className={s.scoreStatsSkel}>
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className={s.scoreStatItem}>
            <Blk className={s.scoreStatLabel} />
            <Blk className={s.scoreStatValue} />
          </div>
        ))}
      </div>
    </div>
  );
}

function SkeletonTopicCard() {
  return (
    <div className={s.topicCard}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Blk className={s.topicName} />
        <Blk className={s.topicPct} />
      </div>
      <Blk className={s.topicBar} />
      <Blk className={s.topicDetail} />
    </div>
  );
}

export default function ResultsSkeleton() {
  return (
    <>
      <SkeletonScoreHero />

      {/* Tab strip placeholder */}
      <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
        {[120, 120].map((w, i) => (
          <Blk
            key={i}
            className={s.block}
            style={{
              height: 40,
              width: w,
              borderRadius: "var(--radius-md)",
            }}
          />
        ))}
      </div>

      {/* Topic cards */}
      <div className={s.topicGrid}>
        {Array.from({ length: 8 }, (_, i) => (
          <SkeletonTopicCard key={i} />
        ))}
      </div>
    </>
  );
}
