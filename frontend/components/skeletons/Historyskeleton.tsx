import s from '@/styles/Skeleton.module.css';

const Blk = ({ className }: { className?: string }) => (
  <div className={`${s.block} ${className || ''}`} />
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