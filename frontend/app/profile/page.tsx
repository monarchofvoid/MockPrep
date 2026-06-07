'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import ProfileSkeleton from '@/components/skeletons/Profileskeleton';
import { getProfile, updateProfile } from '@/lib/api';
import { useAuthStore } from '@/stores/authStore';
import styles from '@/styles/ProfilePage.module.css';


// ── Constants ─────────────────────────────────────────────────────────────────

const EXAMS   = ['CUET', 'GATE', 'JEE', 'UPSC', 'NEET', 'CAT', 'OTHER'];
const YEARS   = [2025, 2026, 2027, 2028];
const AVATARS = [
  { code: 'owl',       emoji: '🦉', label: 'Owl'       },
  { code: 'fox',       emoji: '🦊', label: 'Fox'       },
  { code: 'bear',      emoji: '🐻', label: 'Bear'      },
  { code: 'cat',       emoji: '🐱', label: 'Cat'       },
  { code: 'robot',     emoji: '🤖', label: 'Robot'     },
  { code: 'astronaut', emoji: '👨‍🚀', label: 'Astronaut' },
  { code: 'penguin',   emoji: '🐧', label: 'Penguin'   },
  { code: 'tiger',     emoji: '🐯', label: 'Tiger'     },
];

// ── Types ─────────────────────────────────────────────────────────────────────

interface ProfileForm {
  preparing_exam:  string;
  target_year:     string | number;
  subject_focus:   string;
  avatar:          string;
  daily_goal_mins: number;
  bio:             string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function computeCompletion(form: ProfileForm): number {
  const fields = [
    form.avatar,
    form.preparing_exam,
    form.target_year,
    form.subject_focus?.trim(),
    form.bio?.trim(),
  ];
  return Math.round((fields.filter(Boolean).length / fields.length) * 100);
}

function formatGoal(mins: number): string {
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const router    = useRouter();
  const { user }  = useAuthStore();
  const firstName = (user?.name || '').split(' ')[0] || 'Your Profile';

  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [success, setSuccess] = useState(false);
  const [error,   setError]   = useState('');

  const [form, setForm] = useState<ProfileForm>({
    preparing_exam:  '',
    target_year:     '',
    subject_focus:   '',
    avatar:          '',
    daily_goal_mins: 60,
    bio:             '',
  });

  useEffect(() => {
    getProfile()
      .then((data) => {
        setForm({
          preparing_exam:  data.preparing_exam  || '',
          target_year:     data.target_year     || '',
          subject_focus:   data.subject_focus   || '',
          avatar:          data.avatar          || '',
          daily_goal_mins: (data.daily_goal_mins as number) || 60,
          bio:             data.bio             || '',
        });
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.message?.includes('Session expired')) router.push('/');
      })
      .finally(() => setLoading(false));
  }, [router]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setSuccess(false);
  };

  const handleAvatarSelect = (code: string) => {
    setForm((prev) => ({ ...prev, avatar: code }));
    setSuccess(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess(false);

    const payload: Record<string, unknown> = {};
    if (form.preparing_exam)       payload.preparing_exam  = form.preparing_exam;
    if (form.target_year)          payload.target_year     = parseInt(String(form.target_year));
    if (form.subject_focus?.trim()) payload.subject_focus  = form.subject_focus.trim();
    if (form.avatar)               payload.avatar          = form.avatar;
    if (form.daily_goal_mins)      payload.daily_goal_mins = parseInt(String(form.daily_goal_mins));
    if (form.bio?.trim())          payload.bio             = form.bio.trim();

    try {
      await updateProfile(payload);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save profile.');
    } finally {
      setSaving(false);
    }
  };

  const selectedAvatar = AVATARS.find((a) => a.code === form.avatar);
  const completion     = computeCompletion(form);
  const sliderPct      = ((Number(form.daily_goal_mins) - 15) / (480 - 15)) * 100;

  if (loading) {
    return (
      <div className={styles.page}>
        <Navbar />
        <ProfileSkeleton />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Navbar />

      <div className={styles.container}>

        {/* ── Hero Card ── */}
        <div className={styles.hero}>
          <div className={styles.heroLeft}>
            <div className={styles.heroAvatar}>
              <span className={styles.heroAvatarEmoji}>
                {selectedAvatar ? selectedAvatar.emoji : '👤'}
              </span>
              <svg className={styles.completionRing} viewBox="0 0 56 56">
                <circle cx="28" cy="28" r="24" className={styles.ringTrack} />
                <circle
                  cx="28" cy="28" r="24"
                  className={styles.ringFill}
                  strokeDasharray={`${(completion / 100) * 150.8} 150.8`}
                />
              </svg>
            </div>

            <div className={styles.heroInfo}>
              <h1 className={styles.heroTitle}>{firstName}</h1>
              <p className={styles.heroSubtitle}>
                {form.preparing_exam
                  ? `Preparing for ${form.preparing_exam}${form.target_year ? ` · ${form.target_year}` : ''}`
                  : 'Personalise VYAS to match your goals'}
              </p>
              <div className={styles.completionRow}>
                <div className={styles.completionBar}>
                  <div className={styles.completionFill} style={{ width: `${completion}%` }} />
                </div>
                <span className={styles.completionLabel}>{completion}% complete</span>
              </div>
            </div>
          </div>

          <div className={styles.heroStats}>
            <div className={styles.heroStat}>
              <span className={styles.heroStatValue}>{formatGoal(Number(form.daily_goal_mins))}</span>
              <span className={styles.heroStatLabel}>Daily goal</span>
            </div>
            {form.preparing_exam && (
              <div className={styles.heroStat}>
                <span className={styles.heroStatValue}>{form.preparing_exam}</span>
                <span className={styles.heroStatLabel}>Target exam</span>
              </div>
            )}
          </div>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>

          {/* ── Avatar Selection ── */}
          <section className={styles.section}>
            <div className={styles.sectionHead}>
              <span className={styles.sectionIcon}>🎭</span>
              <div>
                <h2 className={styles.sectionTitle}>Choose Your Avatar</h2>
                <p className={styles.sectionNote}>Your visual identity across VYAS</p>
              </div>
            </div>
            <div className={styles.avatarGrid}>
              {AVATARS.map((a) => (
                <button
                  type="button"
                  key={a.code}
                  className={`${styles.avatarBtn} ${form.avatar === a.code ? styles.avatarSelected : ''}`}
                  onClick={() => handleAvatarSelect(a.code)}
                  aria-label={`Select ${a.label} avatar`}
                >
                  <span className={styles.avatarEmoji}>{a.emoji}</span>
                  <span className={styles.avatarLabel}>{a.label}</span>
                  {form.avatar === a.code && (
                    <span className={styles.avatarCheck}>✓</span>
                  )}
                </button>
              ))}
            </div>
          </section>

          {/* ── Exam Preferences ── */}
          <section className={styles.section}>
            <div className={styles.sectionHead}>
              <span className={styles.sectionIcon}>🎯</span>
              <div>
                <h2 className={styles.sectionTitle}>Exam Preferences</h2>
                <p className={styles.sectionNote}>
                  Your exam is used as a <strong>hard filter</strong> — you&apos;ll only see papers for this exam
                </p>
              </div>
            </div>

            <div className={styles.row}>
              <div className={styles.field}>
                <label htmlFor="preparing_exam" className={styles.label}>
                  Exam I&apos;m Preparing For
                </label>
                <select
                  id="preparing_exam"
                  name="preparing_exam"
                  value={form.preparing_exam}
                  onChange={handleChange}
                  className={styles.select}
                >
                  <option value="">— Select Exam —</option>
                  {EXAMS.map((e) => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                </select>
              </div>

              <div className={styles.field}>
                <label htmlFor="target_year" className={styles.label}>Target Year</label>
                <select
                  id="target_year"
                  name="target_year"
                  value={String(form.target_year)}
                  onChange={handleChange}
                  className={styles.select}
                >
                  <option value="">— Select Year —</option>
                  {YEARS.map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className={styles.field}>
              <label htmlFor="subject_focus" className={styles.label}>
                Subject Focus <span className={styles.optional}>(optional)</span>
              </label>
              <input
                id="subject_focus"
                name="subject_focus"
                type="text"
                value={form.subject_focus}
                onChange={handleChange}
                placeholder="e.g. Economics, Business Studies, English"
                className={styles.input}
                maxLength={200}
              />
              <p className={styles.hint}>Comma-separated subjects you want to focus on.</p>
            </div>
          </section>

          {/* ── Study Goal ── */}
          <section className={styles.section}>
            <div className={styles.sectionHead}>
              <span className={styles.sectionIcon}>⏱</span>
              <div>
                <h2 className={styles.sectionTitle}>Daily Study Goal</h2>
                <p className={styles.sectionNote}>How long do you plan to study each day?</p>
              </div>
            </div>

            <div className={styles.goalDisplay}>
              <span className={styles.goalValue}>{formatGoal(Number(form.daily_goal_mins))}</span>
              <span className={styles.goalSuffix}>per day</span>
            </div>

            <div className={styles.sliderWrap}>
              <input
                id="daily_goal_mins"
                name="daily_goal_mins"
                type="range"
                min={15}
                max={480}
                step={15}
                value={form.daily_goal_mins}
                onChange={handleChange}
                className={styles.range}
                style={{ '--slider-pct': `${sliderPct}%` } as React.CSSProperties}
              />
              <div className={styles.rangeLabels}>
                <span>15 min</span>
                <span>2 hrs</span>
                <span>4 hrs</span>
                <span>8 hrs</span>
              </div>
            </div>
          </section>

          {/* ── About You ── */}
          <section className={styles.section}>
            <div className={styles.sectionHead}>
              <span className={styles.sectionIcon}>✏️</span>
              <div>
                <h2 className={styles.sectionTitle}>About You</h2>
                <p className={styles.sectionNote}>Tell VYAS about your preparation journey</p>
              </div>
            </div>

            <div className={styles.field}>
              <textarea
                id="bio"
                name="bio"
                value={form.bio}
                onChange={handleChange}
                placeholder="Tell us a bit about your preparation journey…"
                className={styles.textarea}
                rows={3}
                maxLength={300}
              />
              <div className={styles.bioFooter}>
                <p className={styles.hint}>Optional — helps VYAS personalise responses</p>
                <p
                  className={styles.charCount}
                  data-near={form.bio.length > 250 ? 'true' : undefined}
                >
                  {form.bio.length}/300
                </p>
              </div>
            </div>
          </section>

          {error && (
            <div className={styles.errorBox}>
              <span>⚠</span>
              <span>{error}</span>
            </div>
          )}

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.cancelBtn}
              onClick={() => router.push('/dashboard')}
            >
              ← Dashboard
            </button>
            <button
              type="submit"
              className={`${styles.saveBtn} ${success ? styles.saveBtnSuccess : ''}`}
              disabled={saving}
            >
              {saving ? (
                <><span className={styles.btnSpinner} /> Saving…</>
              ) : success ? (
                <>✓ Saved!</>
              ) : (
                <>Save Profile</>
              )}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}