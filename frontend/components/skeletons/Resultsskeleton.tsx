import s from '@/styles/Skeleton.module.css';

const Blk = ({ className, style }: { className?: string; style?: React.CSSProperties }) => (
  <div className={`${s.block} ${className || ''}`} style={style} />
);

function SkeletonScoreHero() {
  return (
    <div className={s.scoreHero}>
      <Blk className={s.scoreCircle} />
      <div className={s.scoreBreakdownSkel}>
        {[0, 1, 2].map((i) => (
          <div key={i} className={s.scoreBreakItem}>
            <Blk className={s.scoreBreakVal} />
            <Blk className={s.scoreBreakLbl} />
          </div>
        ))}
      </div>
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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
      <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
        {[120, 120].map((w, i) => (
          <Blk key={i} style={{ height: 40, width: w, borderRadius: 'var(--radius-md)' }} />
        ))}
      </div>
      <div className={s.topicGrid}>
        {Array.from({ length: 8 }, (_, i) => (
          <SkeletonTopicCard key={i} />
        ))}
      </div>
    </>
  );
}