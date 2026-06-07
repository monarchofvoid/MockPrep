import s from '@/styles/Skeleton.module.css';

const Blk = ({ className, style }: { className?: string; style?: React.CSSProperties }) => (
  <div className={`${s.block} ${className || ''}`} style={style} />
);

function SkeletonMockCard() {
  return (
    <div className={s.mockCard}>
      <div className={s.mockCardHeader}>
        <Blk className={s.mockBadge} />
        <Blk className={s.mockDifficulty} />
      </div>
      <Blk className={s.mockTitle} />
      <Blk className={s.mockYear} />
      <div className={s.mockMetaRow}>
        <Blk className={s.mockMetaBox} />
        <Blk className={s.mockMetaBox} />
        <Blk className={s.mockMetaBox} />
      </div>
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