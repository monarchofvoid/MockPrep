/**
 * ProfileSkeleton
 * Mirrors ProfilePage's form sections while the profile API call resolves.
 * Sections: header, avatar grid, exam prefs, daily goal, bio.
 */

import s from "./Skeleton.module.css";

const Blk = ({ className, style }) => (
  <div className={`${s.block} ${className || ""}`} style={style} />
);

export default function ProfileSkeleton() {
  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "32px 24px 64px" }}>

      {/* Header: avatar circle + title */}
      <div className={s.profileHeader}>
        <Blk className={s.avatarCircle} />
        <div className={s.profileTitleGroup}>
          <Blk className={s.profileTitle} />
          <Blk className={s.profileSub} />
        </div>
      </div>

      {/* Avatar picker section */}
      <div className={s.profileSection}>
        <Blk className={s.profileSectionTitle} />
        <div className={s.avatarGrid}>
          {Array.from({ length: 8 }, (_, i) => (
            <Blk key={i} className={s.avatarBtn} />
          ))}
        </div>
      </div>

      {/* Exam preferences section */}
      <div className={s.profileSection}>
        <Blk className={s.profileSectionTitle} />
        <div className={s.formRow}>
          <div>
            <Blk className={s.formLabel} />
            <Blk className={s.formField} />
          </div>
          <div>
            <Blk className={s.formLabel} />
            <Blk className={s.formField} />
          </div>
        </div>
        <Blk className={s.formLabel} />
        <Blk className={s.formField} />
      </div>

      {/* Daily goal section */}
      <div className={s.profileSection}>
        <Blk className={s.profileSectionTitle} />
        <Blk className={s.formLabel} style={{ marginBottom: 12 }} />
        <Blk className={s.formField} />
      </div>

      {/* Bio section */}
      <div className={s.profileSection}>
        <Blk className={s.profileSectionTitle} />
        <Blk className={s.formLabel} />
        <Blk className={s.textarea} />
      </div>

      {/* Actions */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
        <Blk style={{ height: 44, width: 140, borderRadius: "var(--radius-md)" }} />
        <Blk style={{ height: 44, width: 120, borderRadius: "var(--radius-md)" }} />
      </div>
    </div>
  );
}
