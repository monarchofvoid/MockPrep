/**
 * DashboardSkeleton
 * Mirrors the exact structure of the Dashboard's data-driven sections:
 *   1. Stats row  (3 stat cards)
 *   2. Chart grid (2 panels)
 *   3. Recent attempts section (table with 5 rows)
 *
 * The Welcome header is NOT skeletonised — it renders immediately
 * from AuthContext (no API call needed for user.name).
 */

import s from "./Skeleton.module.css";

/* ── Atoms ─────────────────────────────────────────────────────── */
const Blk = ({ className, style }) => (
  <div className={`${s.block} ${className || ""}`} style={style} />
);

/* ── Stat card ─────────────────────────────────────────────────── */
function SkeletonStatCard() {
  return (
    <div className={s.statCard}>
      <Blk className={s.statLabel} />
      <Blk className={s.statValue} style={{ marginTop: 4 }} />
      <Blk className={s.statSub}   style={{ marginTop: 8 }} />
    </div>
  );
}

/* ── Chart panel ───────────────────────────────────────────────── */
function SkeletonChartPanel() {
  return (
    <div className={s.panel}>
      <Blk className={s.panelTitle} />
      <Blk className={s.panelSub}   style={{ marginTop: 6 }} />
      <Blk className={`${s.block} ${s.chartBox}`} style={{ marginTop: 16 }} />
    </div>
  );
}

/* ── Table row ─────────────────────────────────────────────────── */
function SkeletonTableRow() {
  return (
    <div className={s.tableRow}>
      <Blk className={s.tableCellBold} />
      <Blk className={s.tableCell} />
      <Blk className={s.tableCell} />
      <Blk className={s.tableCell} />
      <Blk className={s.tableCell} />
      <Blk className={s.tableCellSmall} />
      <Blk className={s.tableCell} style={{ maxWidth: 80 }} />
    </div>
  );
}

/* ── Main export ───────────────────────────────────────────────── */
export default function DashboardSkeleton() {
  return (
    <>
      {/* Stats row */}
      <div className={s.statsRow}>
        <SkeletonStatCard />
        <SkeletonStatCard />
        <SkeletonStatCard />
      </div>

      {/* Charts */}
      <div className={s.chartGrid}>
        <SkeletonChartPanel />
        <SkeletonChartPanel />
      </div>

      {/* Recent attempts section */}
      <div className={s.section}>
        <div className={s.sectionHeader}>
          <div style={{ flex: 1 }}>
            <Blk className={s.sectionTitle} />
            <Blk className={s.sectionSub} style={{ marginTop: 8 }} />
          </div>
          <Blk className={s.sectionBtn} />
        </div>
        {/* Table header */}
        <div className={s.tableHeader}>
          {["45%","12%","16%","12%","8%","10%"].map((w, i) => (
            <Blk key={i} className={s.tableHeaderCell} style={{ flex: "none", width: w }} />
          ))}
        </div>
        {/* 5 data rows */}
        {Array.from({ length: 5 }, (_, i) => (
          <SkeletonTableRow key={i} />
        ))}
      </div>
    </>
  );
}
