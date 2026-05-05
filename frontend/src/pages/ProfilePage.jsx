/**
 * VYAS v0.6 — Profile Page
 * FIX: Added <Navbar /> — was completely missing, causing the navbar to
 * vanish whenever the user navigated to /profile.
 */

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getProfile, updateProfile } from "../api/client";
import Navbar from "../components/Navbar";
import styles from "../styles/ProfilePage.module.css";

const EXAMS   = ["CUET", "GATE", "JEE", "UPSC", "NEET", "CAT", "OTHER"];
const YEARS   = [2025, 2026, 2027, 2028];
const AVATARS = [
  { code: "owl",       emoji: "🦉", label: "Owl"       },
  { code: "fox",       emoji: "🦊", label: "Fox"       },
  { code: "bear",      emoji: "🐻", label: "Bear"      },
  { code: "cat",       emoji: "🐱", label: "Cat"       },
  { code: "robot",     emoji: "🤖", label: "Robot"     },
  { code: "astronaut", emoji: "👨‍🚀", label: "Astronaut" },
  { code: "penguin",   emoji: "🐧", label: "Penguin"   },
  { code: "tiger",     emoji: "🐯", label: "Tiger"     },
];

export default function ProfilePage() {
  const navigate  = useNavigate();
  const [loading, setLoading]   = useState(true);
  const [saving,  setSaving]    = useState(false);
  const [success, setSuccess]   = useState(false);
  const [error,   setError]     = useState("");

  const [form, setForm] = useState({
    preparing_exam:  "",
    target_year:     "",
    subject_focus:   "",
    avatar:          "",
    daily_goal_mins: 60,
    bio:             "",
  });

  useEffect(() => {
    getProfile()
      .then(d => {
        setForm({
          preparing_exam:  d.preparing_exam  || "",
          target_year:     d.target_year     || "",
          subject_focus:   d.subject_focus   || "",
          avatar:          d.avatar          || "",
          daily_goal_mins: d.daily_goal_mins || 60,
          bio:             d.bio             || "",
        });
      })
      .catch(err => {
        if (err.message?.includes("Session expired")) navigate("/");
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  const handleChange = e => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
    setSuccess(false);
  };

  const handleAvatarSelect = code => {
    setForm(prev => ({ ...prev, avatar: code }));
    setSuccess(false);
  };

  const handleSubmit = async e => {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess(false);

    const payload = {};
    if (form.preparing_exam)       payload.preparing_exam  = form.preparing_exam;
    if (form.target_year)          payload.target_year     = parseInt(form.target_year);
    if (form.subject_focus.trim()) payload.subject_focus   = form.subject_focus.trim();
    if (form.avatar)               payload.avatar          = form.avatar;
    if (form.daily_goal_mins)      payload.daily_goal_mins = parseInt(form.daily_goal_mins);
    if (form.bio.trim())           payload.bio             = form.bio.trim();

    try {
      await updateProfile(payload);
      setSuccess(true);
    } catch (err) {
      setError(err.message || "Failed to save profile. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const selectedAvatar = AVATARS.find(a => a.code === form.avatar);

  if (loading) {
    return (
      <div className={styles.page}>
        <Navbar />
        <div className={styles.loadingWrap}>
          <div className={styles.spinner} />
          <p>Loading your profile…</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Navbar />

      <div className={styles.container}>

        {/* ── Header ── */}
        <div className={styles.header}>
          <div className={styles.avatarDisplay}>
            {selectedAvatar ? selectedAvatar.emoji : "👤"}
          </div>
          <div>
            <h1 className={styles.title}>Your Profile</h1>
            <p className={styles.subtitle}>
              Personalise VYAS to match your exam goals and study style.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>

          {/* ── Avatar Selector ── */}
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Choose Your Avatar</h2>
            <div className={styles.avatarGrid}>
              {AVATARS.map(a => (
                <button
                  type="button"
                  key={a.code}
                  className={`${styles.avatarBtn} ${form.avatar === a.code ? styles.avatarSelected : ""}`}
                  onClick={() => handleAvatarSelect(a.code)}
                  aria-label={`Select ${a.label} avatar`}
                >
                  <span className={styles.avatarEmoji}>{a.emoji}</span>
                  <span className={styles.avatarLabel}>{a.label}</span>
                </button>
              ))}
            </div>
          </section>

          {/* ── Exam Preferences ── */}
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Exam Preferences</h2>
            <p className={styles.sectionNote}>
              Your preparing exam is used as a <strong>hard filter</strong> for
              mock recommendations — you will only see papers for this exam.
            </p>

            <div className={styles.row}>
              <div className={styles.field}>
                <label htmlFor="preparing_exam" className={styles.label}>
                  Exam I'm Preparing For
                </label>
                <select
                  id="preparing_exam"
                  name="preparing_exam"
                  value={form.preparing_exam}
                  onChange={handleChange}
                  className={styles.select}
                >
                  <option value="">— Select Exam —</option>
                  {EXAMS.map(e => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                </select>
              </div>

              <div className={styles.field}>
                <label htmlFor="target_year" className={styles.label}>
                  Target Year
                </label>
                <select
                  id="target_year"
                  name="target_year"
                  value={form.target_year}
                  onChange={handleChange}
                  className={styles.select}
                >
                  <option value="">— Select Year —</option>
                  {YEARS.map(y => (
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

          {/* ── Study Goals ── */}
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>Daily Study Goal</h2>
            <div className={styles.field}>
              <label htmlFor="daily_goal_mins" className={styles.label}>
                Minutes per day: <strong>{form.daily_goal_mins} min</strong>
              </label>
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
              />
              <div className={styles.rangeLabels}>
                <span>15 min</span>
                <span>2 hrs</span>
                <span>4 hrs</span>
                <span>8 hrs</span>
              </div>
            </div>
          </section>

          {/* ── Bio ── */}
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>About You</h2>
            <div className={styles.field}>
              <label htmlFor="bio" className={styles.label}>
                Short Bio <span className={styles.optional}>(optional)</span>
              </label>
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
              <p className={styles.charCount}>{form.bio.length}/300</p>
            </div>
          </section>

          {error   && <p className={styles.errorMsg}>{error}</p>}
          {success && <p className={styles.successMsg}>✅ Profile saved successfully!</p>}

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.cancelBtn}
              onClick={() => navigate("/dashboard")}
            >
              Back to Dashboard
            </button>
            <button
              type="submit"
              className={styles.saveBtn}
              disabled={saving}
            >
              {saving ? "Saving…" : "Save Profile"}
            </button>
          </div>

        </form>
      </div>
    </div>
  );
}