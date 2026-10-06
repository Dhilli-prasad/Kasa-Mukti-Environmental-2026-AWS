import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, BarChart3, Bell, Bot, Camera, ChevronRight, CircleUserRound,
  ClipboardCheck, Database, Globe2, History, Leaf, LoaderCircle, MapPin, Menu, MessageCircle,
  PackageCheck, Recycle, ScanLine, Send, ShieldCheck, Sparkles, Trophy, Truck, Users, Wifi, WifiOff, X
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import Scanner from "./components/Scanner";
import { apiRequest, hasApi } from "./lib/api";
import { authConfigured, clearDemoSession, confirmSignUp, forgotPassword, getDemoSession, getSession, signIn, signInDemo, signOut, signUp } from "./lib/auth";
import { demoLeaderboard, demoRecoveryHistory, demoSeedData, demoSteps, demoWardStats } from "./data/mockData";
import { Card, EmptyState, LinkButton, SectionTitle, StatCard, StatusBadge } from "./components/ui";
import { cognitoConfigured, isDemoMode } from "./lib/config";
import { CollectionCenters, ImpactCards, MaterialBank, NotificationCenter } from "./components/CircularSurfaces";
import { useTranslation } from "./lib/i18n";

const ROLES = [
  ["CITIZEN", "Citizen"], ["FARMER", "Farmer"], ["MUNICIPAL_WORKER", "Municipal Worker"],
  ["MUNICIPAL_OFFICER", "Municipal Officer"], ["RECOVERY_PARTNER", "Recovery Partner"], ["ADMIN", "Administrator"]
];
const DEMO_MODE = isDemoMode;
const pagesForRole = (role, t) => ["CITIZEN", "FARMER"].includes(role)
  ? [["overview", t("navigation.overview"), Activity], ["scan", t("navigation.scanWaste"), ScanLine], ["points", t("navigation.greenPoints"), Trophy], ["chat", t("navigation.askAi"), MessageCircle]]
  : role === "MUNICIPAL_WORKER"
    ? [["overview", t("navigation.verificationQueue"), ClipboardCheck], ["batches", t("navigation.batches"), PackageCheck]]
    : ["MUNICIPAL_OFFICER", "ADMIN"].includes(role)
        ? [["overview", t("navigation.municipalDashboard"), BarChart3], ["inventory", t("navigation.inventory"), Database], ["projects", t("navigation.projects"), Globe2], ["chat", t("navigation.copilot"), Bot]]
      : [["overview", t("navigation.partnerDashboard"), Recycle], ["history", t("navigation.recoveryHistory"), History]];

function NetworkStatus({ online, loading, demo = false }) {
  const { t } = useTranslation();
  return <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${online ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-300" : "border-rose-400/25 bg-rose-400/10 text-rose-300"}`}>
    {loading ? <LoaderCircle size={13} className="animate-spin" /> : demo ? <Sparkles size={13} /> : online ? <Wifi size={13} /> : <WifiOff size={13} />}
    {loading ? t("status.syncing") : demo ? t("status.demo") : online ? t("status.live") : t("status.offline")}
  </span>;
}

function AuthLoading() {
  return <div className="flex min-h-screen items-center justify-center bg-[#06110e] text-emerald-300"><LoaderCircle className="animate-spin" size={32} /></div>;
}

function AuthPage({ configured, error, onSignedIn, demo = false }) {
  const { t } = useTranslation();
  const [register, setRegister] = useState(false);
  const [reset, setReset] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [confirmationCode, setConfirmationCode] = useState("");
  const [role, setRole] = useState("CITIZEN");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(error);
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true); setMessage("");
    try {
      if (demo) {
        onSignedIn(signInDemo(role, email));
        setMessage(t("auth.loginSuccess"));
      } else if (confirm) {
        await confirmSignUp(email, confirmationCode.trim());
        setMessage(t("auth.emailVerified"));
        setConfirm(false);
      } else if (reset) {
        await forgotPassword(email);
        setMessage(t("auth.resetSent"));
        setReset(false);
      } else if (register) {
        await signUp(email, password);
        setMessage(t("auth.verificationSent"));
        setConfirm(true);
      } else onSignedIn(await signIn(email, password));
    } catch (authError) { setMessage(authError.message || t("auth.failed")); }
    finally { setBusy(false); }
  };
  return <div className="flex min-h-screen items-center justify-center bg-[#06110e] px-4 text-white">
    <motion.form initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} onSubmit={submit} className="w-full max-w-md rounded-3xl border border-white/10 bg-white/[.06] p-8 shadow-2xl backdrop-blur-xl">
      <div className="mb-8"><div className="mb-4 inline-flex rounded-2xl bg-emerald-400/15 p-3 text-emerald-300"><Leaf /></div><h1 className="text-3xl font-black">{t("auth.welcome")}</h1><p className="mt-2 text-sm text-slate-400">{t("auth.subtitle")}</p></div>
      {demo && <div className="mb-4 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-amber-200">{t("auth.demoBanner")}</div>}
      {!demo && !configured && <div className="mb-4 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-amber-200">{t("auth.cognito")}</div>}
      {demo && <label className="mb-4 block text-sm text-slate-300">{t("auth.demoRole")}<select aria-label={t("auth.demoRole")} value={role} onChange={(event) => setRole(event.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-white outline-none focus:border-emerald-400">{ROLES.map(([value]) => <option key={value} value={value} className="bg-[#071411]">{t(`roles.${value}`)}</option>)}</select></label>}
      {message && <div className="mb-4 rounded-xl border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200">{message}</div>}
      <label className="mb-4 block text-sm text-slate-300">{t("auth.email")}<input required type="email" value={email} placeholder={demo ? "citizen@example.com" : ""} onChange={(e) => setEmail(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-white outline-none focus:border-emerald-400" /></label>
      {confirm && <label className="mb-4 block text-sm text-slate-300">{t("auth.verificationCode")}<input required value={confirmationCode} onChange={(e) => setConfirmationCode(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-white outline-none focus:border-emerald-400" /></label>}
      {!demo && !confirm && <label className="mb-6 block text-sm text-slate-300">{t("auth.password")}<input required={!reset} minLength={8} type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-white outline-none focus:border-emerald-400" /></label>}
      <button disabled={busy || (!demo && !configured)} className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-400 px-4 py-3 font-bold text-[#06110e] disabled:cursor-not-allowed disabled:opacity-50">{busy && <LoaderCircle size={17} className="animate-spin" />}{demo ? t("auth.continue") : confirm ? t("auth.verify") : reset ? t("auth.reset") : register ? t("auth.create") : t("auth.signIn")}</button>
      {!demo && <div className="mt-4 flex justify-between text-sm text-emerald-300"><button type="button" onClick={() => { setRegister(!register); setReset(false); setMessage(""); }}>{register ? t("auth.registered") : t("auth.register")}</button><button type="button" onClick={() => { setReset(!reset); setRegister(false); setMessage(""); }}>{reset ? t("auth.back") : t("auth.forgot")}</button></div>}
    </motion.form>
  </div>;
}

export default function App() {
  const { language, setLanguage, languages, t } = useTranslation();
  const [role, setRole] = useState("CITIZEN");
  const [page, setPage] = useState("overview");
  const [mobileNav, setMobileNav] = useState(false);
  const [loading, setLoading] = useState(false);
  const [online, setOnline] = useState(DEMO_MODE || (navigator.onLine && hasApi()));
  const [notice, setNotice] = useState(null);
  const [data, setData] = useState(() => DEMO_MODE ? structuredClone(demoSeedData) : { scans: [], pending: [], inventory: [], batches: [], centers: [], matches: [], projects: [], profile: null, analytics: null });
  const [demoStep, setDemoStep] = useState(0);
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(!DEMO_MODE && !getDemoSession());
  const [authError, setAuthError] = useState("");
  const [userId] = useState(() => localStorage.getItem("kasamukti-user") || `citizen-${crypto.randomUUID().slice(0, 8)}`);
  const displayRole = t(`roles.${role}`);
  const navItems = pagesForRole(role, t);

  useEffect(() => { localStorage.setItem("kasamukti-user", userId); }, [userId]);
  useEffect(() => {
    if (DEMO_MODE) {
      const demoSession = getDemoSession();
      if (demoSession) {
        setSession(demoSession);
        setRole(demoSession.role);
      }
      setAuthLoading(false);
      return;
    }
    getSession().then((value) => {
      setSession(value);
      if (value?.role) setRole(value.role);
    }).catch((error) => setAuthError(error.message)).finally(() => setAuthLoading(false));
  }, []);
  useEffect(() => { setPage("overview"); setMobileNav(false); }, [role]);
  const request = useCallback(async (path, options = {}) => {
    setLoading(true);
    try {
      const payload = await apiRequest(path, { ...options, role, userId });
      setOnline(true);
      return payload;
    } catch (error) {
      setOnline(false);
      throw error;
    } finally { setLoading(false); }
  }, [role, userId]);
  const refresh = useCallback(async () => {
    if (DEMO_MODE) return;
    try {
      const [inventory, centers, profile, analytics, matches, projects] = await Promise.all([
        ["MUNICIPAL_WORKER", "MUNICIPAL_OFFICER", "RECOVERY_PARTNER"].includes(role) ? request("/inventory") : Promise.resolve({ inventory: [], batches: [], scans: [], pending: [] }),
        ["CITIZEN", "FARMER"].includes(role) ? request("/centers") : Promise.resolve({ centers: [] }),
        ["CITIZEN", "FARMER"].includes(role) ? request("/profile") : Promise.resolve({}),
        ["MUNICIPAL_OFFICER"].includes(role) ? request("/analytics") : Promise.resolve({}),
        ["RECOVERY_PARTNER", "MUNICIPAL_OFFICER"].includes(role) ? request("/matches") : Promise.resolve({ matches: [] }),
        role === "MUNICIPAL_OFFICER" ? request("/projects") : Promise.resolve({ projects: [] })
      ]);
      setData({ ...inventory, centers: centers.centers || [], profile, analytics, matches: matches.matches || [], projects: projects.projects || [] });
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    }
  }, [request, role]);
  useEffect(() => { if (!DEMO_MODE) refresh(); }, [refresh]);
  useEffect(() => { if (!notice) return undefined; const timer = setTimeout(() => setNotice(null), 5000); return () => clearTimeout(timer); }, [notice]);
  useEffect(() => {
    if (!DEMO_MODE || !session) return;
    const notification = JSON.parse(localStorage.getItem("kasamukti-demo-notifications") || "null");
    if (notification?.userId === session.userId) setNotice({ type: "success", text: `DEMO EMAIL simulated for ${notification.recipient}.` });
  }, [session]);

  const handleAnalyzed = () => { setNotice({ type: "success", text: "AI result saved to AWS. Verify the physical deposit to unlock GreenPoints." }); refresh(); };
  const handleVerify = async (scanId, weight, centerId) => {
    try {
      await request("/collection-events", { method: "POST", body: JSON.stringify({ scanId, verifiedWeight: weight, centerId, idempotencyKey: `${scanId}-${centerId}-${weight}` }) });
      setNotice({ type: "success", text: "Deposit verified. GreenPoints and material inventory updated." }); refresh();
    } catch (error) { setNotice({ type: "error", text: error.message }); }
  };

  if (authLoading) return <AuthLoading />;
  if (!session) return <AuthPage demo={DEMO_MODE} configured={cognitoConfigured && authConfigured()} error={authError} onSignedIn={(value) => { setSession(value); setRole(value.role); }} />;

  return <div className="min-h-screen">
    <header className="sticky top-0 z-30 border-b border-white/5 bg-[#071411]/90 backdrop-blur-xl">
      <nav className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-5 py-4 lg:px-8">
        <button onClick={() => setPage("overview")} className="flex items-center gap-3 text-left"><span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-400 text-[#071411]"><Recycle size={22} /></span><span><span className="block font-display text-lg font-bold">KasaMukti</span><span className="block text-[10px] uppercase tracking-[.25em] text-emerald-300/70">Circular Bharat</span></span></button>
        <div className="hidden items-center gap-2 md:flex">{DEMO_MODE && <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-1.5 text-xs font-bold text-amber-200">SIMULATED DEMO</span>}<NetworkStatus online={online} loading={loading} demo={DEMO_MODE} />        <label className="flex items-center gap-2 text-xs text-slate-400"><Globe2 size={15} /><span className="sr-only">{t("language.label")}</span><select aria-label={t("language.label")} value={language} onChange={(event) => setLanguage(event.target.value)} className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-slate-300 outline-none">{languages.map(([code, label]) => <option key={code} value={code} className="bg-[#071411]">{label}</option>)}</select></label><button onClick={() => { if (DEMO_MODE) clearDemoSession(); else signOut(); setSession(null); }} className="rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-400 hover:text-white">{t("status.signOut")}</button><Bell size={18} className="text-slate-400" /><CircleUserRound size={23} className="text-slate-400" /></div>
        <button onClick={() => setMobileNav((value) => !value)} className="rounded-xl border border-white/10 p-2 text-slate-300 md:hidden">{mobileNav ? <X size={19} /> : <Menu size={19} />}</button>
      </nav>
    </header>
    <div className="mx-auto flex max-w-[1500px]">
      <aside className={`fixed inset-y-[73px] left-0 z-20 w-72 border-r border-white/5 bg-[#081713] p-5 transition-transform md:sticky md:top-[73px] md:block md:h-[calc(100vh-73px)] md:translate-x-0 ${mobileNav ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="mb-6 md:hidden"><NetworkStatus online={online} loading={loading} demo={DEMO_MODE} /></div>
        <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[.2em] text-slate-600">{t("navigation.workspace")}</p>
        <div className="space-y-1">{navItems.map(([value, label, Icon]) => <button key={value} onClick={() => { setPage(value); setMobileNav(false); }} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm transition ${page === value ? "bg-emerald-400/10 font-semibold text-emerald-300" : "text-slate-400 hover:bg-white/[.03] hover:text-white"}`}><Icon size={17} />{label}{page === value && <ChevronRight size={14} className="ml-auto" />}</button>)}</div>
        <p className="mb-3 mt-8 px-3 text-[10px] font-bold uppercase tracking-[.2em] text-slate-600">{t("navigation.role")}</p>
        {DEMO_MODE ? <select aria-label={t("navigation.role")} value={role} onChange={(event) => setRole(event.target.value)} className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-slate-300 outline-none focus:border-emerald-400">{ROLES.map(([value]) => <option key={value} value={value} className="bg-[#071411]">{t(`roles.${value}`)}</option>)}</select> : <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[.04] px-3 py-3 text-sm text-emerald-200">{displayRole}<span className="mt-1 block text-[10px] text-slate-500">{t("status.cognitoGroup")}</span></div>}
        <div className="mt-8 rounded-2xl border border-emerald-400/15 bg-emerald-400/[.04] p-4"><p className="flex items-center gap-2 text-xs font-semibold text-emerald-300"><ShieldCheck size={15} /> {t("trust.title")}</p><p className="mt-2 text-xs leading-5 text-slate-500">{t("trust.body")}</p></div>
      </aside>
      <main className="min-w-0 flex-1 px-5 py-8 lg:px-10">
        {DEMO_MODE && <DemoJourney step={demoStep} setStep={setDemoStep} setRole={setRole} setPage={setPage} setData={setData} />}
        <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[.24em] text-emerald-300"><Activity size={14} /> {displayRole} workspace</p><h1 className="font-display text-4xl font-bold tracking-tight md:text-5xl">{pageTitle(page, role, t)}</h1><p className="mt-3 max-w-2xl text-slate-400">{pageDescription(page, role, t)}</p></div>        <button onClick={refresh} disabled={DEMO_MODE} className="flex items-center gap-2 self-start rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-300 hover:border-emerald-400/40 disabled:cursor-default disabled:opacity-60"><Activity size={16} /> {DEMO_MODE ? t("status.seeded") : t("status.refresh")}</button></div>
        <AnimatePresence mode="wait"><motion.div key={`${role}-${page}`} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>{renderPage(page, role, data, DEMO_MODE ? "demo-citizen" : userId, request, handleAnalyzed, handleVerify, setPage, setNotice, DEMO_MODE)}</motion.div></AnimatePresence>
      </main>
    </div>
    <button onClick={() => setPage("chat")} aria-label="Open KasaMukti AI assistant" className="fixed bottom-6 left-6 z-30 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-400 text-[#071411] shadow-xl shadow-emerald-950/50 transition hover:scale-105"><Bot size={23} /></button>
    {notice && <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className={`fixed bottom-6 right-6 z-40 flex max-w-sm items-start gap-3 rounded-2xl border p-4 shadow-2xl backdrop-blur-xl ${notice.type === "error" ? "border-rose-400/30 bg-rose-950/90 text-rose-100" : "border-emerald-400/30 bg-emerald-950/90 text-emerald-100"}`}><ShieldCheck size={18} /><p className="text-sm">{notice.text}</p></motion.div>}
  </div>;
}

function DemoJourney({ step, setStep, setRole, setPage, setData }) {
  const current = demoSteps[step];
  const goTo = (nextStep) => {
    const bounded = Math.max(0, Math.min(nextStep, demoSteps.length - 1));
    const next = demoSteps[bounded];
    setStep(bounded);
    setRole(next.role);
    setPage(next.page);
    if (bounded >= 5) {
      setData((existing) => ({
        ...existing,
        scans: [{ ...demoSeedData.scans[0], status: bounded >= 6 ? "VERIFIED" : "PENDING", verifiedWeight: bounded >= 6 ? 1.2 : undefined, greenPoints: bounded >= 6 ? 120 : undefined, verifiedAt: bounded >= 6 ? "2026-10-05T09:18:00+05:30" : undefined }],
        profile: { ...existing.profile, wallet: { greenPoints: bounded >= 6 ? 120 : 0 }, impact: { verifiedWeightKg: bounded >= 6 ? 1.2 : 0, verifiedDeposits: bounded >= 6 ? 1 : 0 }, badges: bounded >= 6 ? [{ name: "First Safe Return", icon: "shield" }] : [], leaderboard: [{ rank: bounded >= 6 ? 2 : 3, name: "You", userId: "demo-citizen", points: bounded >= 6 ? 120 : 0, ward: "Ward 12" }] },
        inventory: bounded >= 7 ? [{ materialType: "HDPE", quantity: 1, weightKg: 1.2, hazardLevel: "CRITICAL", riskStatus: "SPECIAL_HANDLING", sourceCollectionCenters: ["WARD12-CENTER"] }] : [],
        batches: bounded >= 8 ? [{ batchId: "KM-BATCH-042", materialType: "HDPE", quantity: 1, weightKg: 1.2, hazardLevel: "CRITICAL", qualityStatus: "PASSED", contaminationStatus: "CLEAR", workflowStatus: "READY_FOR_RECOVERY", eligibleRecoveryPathways: ["SPECIALIZED_TREATMENT"], sourceCollectionCenters: ["WARD12-CENTER"] }] : [],
        matches: bounded >= 9 ? [{ matchId: "KM-MATCH-042", batchId: "KM-BATCH-042", partnerName: "SafeCycle Treatment Network", pathway: "SPECIALIZED_TREATMENT", reason: "Verified hazardous-waste handler with HDPE chemical-container capability", status: "ELIGIBLE" }] : [],
        analytics: { ...existing.analytics, totalWasteDivertedKg: bounded >= 6 ? 185.8 : 184.6, verifiedDeposits: bounded >= 6 ? 32 : 31, availableBatches: bounded >= 8 ? 1 : 0 }
      }));
    }
  };
  return <Card className="mb-8 overflow-hidden border-amber-300/20 bg-gradient-to-r from-amber-300/[.08] via-white/[.03] to-emerald-300/[.06] p-5">
    <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
      <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-amber-300/15 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[.18em] text-amber-200">Hackathon demo mode</span><span className="text-xs text-slate-500">Simulated records · real AWS path remains available when disabled</span></div><h2 className="mt-3 font-display text-xl font-semibold">{current.label}</h2><p className="mt-1 text-sm text-slate-400">{current.detail}</p></div>
      <div className="flex shrink-0 items-center gap-2"><button disabled={step === 0} onClick={() => goTo(step - 1)} className="rounded-xl border border-white/10 px-3 py-2 text-xs text-slate-400 disabled:opacity-30">Back</button><button onClick={() => goTo(step + 1)} disabled={step === demoSteps.length - 1} className="rounded-xl bg-emerald-400 px-4 py-2 text-xs font-bold text-[#071411] disabled:opacity-40">{step === demoSteps.length - 1 ? "Impact shown" : "Next moment"}</button></div>
    </div>
    <div className="mt-5 grid grid-cols-11 gap-1.5">{demoSteps.map((item, index) => <button key={item.label} title={item.label} onClick={() => goTo(index)} className={`h-1.5 rounded-full transition ${index <= step ? "bg-emerald-300" : "bg-white/10"}`} />)}</div>
    <div className="mt-3 flex justify-between text-[10px] uppercase tracking-wider text-slate-600"><span>Collect</span><span>Identify</span><span>Verify</span><span>Recover</span><span>Measure</span></div>
  </Card>;
}

function pageTitle(page, role, t) {
  if (page === "scan") return t("pages.scanTitle");
  if (page === "points") return t("pages.pointsTitle");
  if (page === "chat") return role === "MUNICIPAL_OFFICER" ? t("pages.copilotTitle") : t("pages.chatTitle");
  if (role === "MUNICIPAL_WORKER") return t("pages.workerTitle");
  if (role === "MUNICIPAL_OFFICER") return t("pages.officerTitle");
  if (role === "RECOVERY_PARTNER") return t("pages.partnerTitle");
  return role === "FARMER" ? t("pages.farmerTitle") : t("pages.citizenTitle");
}

function pageDescription(page, role, t) {
  if (page === "scan") return t("pages.scanDescription");
  if (page === "points") return t("pages.pointsDescription");
  if (page === "chat") return t("chat.demoSafety");
  if (role === "MUNICIPAL_OFFICER") return t("pages.officerDescription");
  return t("pages.workflowDescription");
}

function renderPage(page, role, data, userId, request, onAnalyzed, onVerify, setPage, setNotice, demoMode = false) {
  if (page === "scan") return <ScanPage userId={userId} data={data} onAnalyzed={onAnalyzed} setPage={setPage} demoMode={demoMode} />;
  if (page === "points") return <PointsPage data={data} />;
  if (page === "chat") return <AssistantPage request={request} />;
  if (role === "MUNICIPAL_WORKER") return page === "batches" ? <WorkerBatches data={data} request={request} setNotice={setNotice} /> : <WorkerDashboard data={data} onVerify={onVerify} />;
  if (role === "MUNICIPAL_OFFICER") return page === "inventory" ? <InventoryPage data={data} /> : page === "projects" ? <PublicProjects data={data} request={request} setNotice={setNotice} /> : <OfficerDashboard data={data} request={request} />;
  if (role === "RECOVERY_PARTNER") return page === "history" ? <RecoveryHistory /> : <PartnerDashboard data={data} request={request} setNotice={setNotice} />;
  return <CitizenDashboard role={role} userId={userId} data={data} setPage={setPage} />;
}

function CitizenDashboard({ role, userId, data, setPage }) {
  const { t } = useTranslation();
  const points = Number(data.profile?.wallet?.greenPoints || 0);
  const scans = (data.scans || []).filter((item) => item.citizenId === userId);
  return <div className="space-y-6"><div className="grid gap-5 lg:grid-cols-[1.3fr_.7fr]"><Card className="relative overflow-hidden bg-gradient-to-br from-emerald-400 to-teal-700 p-7 text-[#062018] shadow-2xl shadow-emerald-950/30"><Globe2 className="absolute -right-5 -top-6 opacity-20" size={190} /><p className="relative text-sm font-semibold opacity-75">{role === "FARMER" ? t("dashboard.farmerWallet") : t("dashboard.wallet")}</p><p className="relative mt-2 font-display text-6xl font-bold">{points}</p><p className="relative mt-4 max-w-sm text-sm opacity-80">{t("dashboard.earned")}</p><button onClick={() => setPage("scan")} className="relative mt-7 flex items-center gap-2 rounded-xl bg-[#062018] px-4 py-3 text-sm font-bold text-emerald-200"><Camera size={17} /> {t("dashboard.scanWaste")} <ChevronRight size={16} /></button></Card><Card className="p-6"><SectionTitle eyebrow={t("dashboard.impact")} title={t("dashboard.footprint")} description={t("dashboard.liveRecords")} /><div className="grid grid-cols-2 gap-3"><MiniMetric value={`${Number(data.profile?.impact?.verifiedWeightKg || 0).toFixed(1)} kg`} label={t("dashboard.diverted")} /><MiniMetric value={data.profile?.impact?.verifiedDeposits || 0} label={t("dashboard.deposits")} /><MiniMetric value={data.profile?.badges?.length || 0} label={t("dashboard.badges")} /><MiniMetric value={`#${(data.profile?.leaderboard || demoLeaderboard).find((item) => item.userId === userId)?.rank || "—"}`} label={t("dashboard.rank")} /></div></Card></div><div className="grid gap-5 md:grid-cols-3"><ActionTile icon={ScanLine} title={t("dashboard.scanWaste")} description={t("dashboard.identify")} onClick={() => setPage("scan")} /><ActionTile icon={MessageCircle} title={t("dashboard.ask")} description={t("dashboard.guidance")} onClick={() => setPage("chat")} /><ActionTile icon={MapPin} title={t("dashboard.find")} description={`${data.centers?.length || 0} live centers available`} onClick={() => document.getElementById("centers")?.scrollIntoView({ behavior: "smooth" })} /></div><div className="grid gap-5 lg:grid-cols-[1fr_.8fr]"><Card className="p-6"><SectionTitle eyebrow={t("dashboard.recentEyebrow")} title={t("dashboard.recentTitle")} action={<LinkButton onClick={() => setPage("points")}>{t("dashboard.history")}</LinkButton>} />{scans.length ? scans.slice(0, 5).map((scan) => <Contribution key={scan.scanId} scan={scan} />) : <EmptyState title={t("dashboard.noTrail")} description={t("dashboard.scanTake")} />}</Card><Card id="centers" className="p-6"><SectionTitle eyebrow={t("dashboard.near")} title={t("dashboard.centers")} /><div className="space-y-3">{data.centers?.length ? data.centers.slice(0, 4).map((center) => <div key={center.centerId} className="rounded-2xl border border-white/10 bg-white/[.03] p-4"><div className="flex items-start justify-between"><div><p className="font-semibold">{center.name}</p><p className="mt-1 text-xs text-slate-500">{center.address || "Address available after setup"}</p></div><MapPin size={17} className="text-emerald-300" /></div><p className="mt-3 text-xs text-emerald-300">{center.openingHours || "Check opening hours"}</p></div>) : <EmptyState title={t("dashboard.noCenters")} description={t("dashboard.addCenters")} />}</div></Card></div></div>;
}

function ScanPage({ userId, data, onAnalyzed, setPage, demoMode }) {
  return <div className="space-y-6"><div className="grid gap-6 xl:grid-cols-[.95fr_1.05fr]"><Scanner citizenId={userId} onAnalyzed={onAnalyzed} demoMode={demoMode} /><Card className="p-6"><SectionTitle eyebrow="Recovery pathways" title="From scan to second life" description="KasaMukti never assumes every item returns to its original manufacturer." /><div className="space-y-3">{["Original producer take-back", "Certified recycler", "Verified reuse partner", "Community upcycling (non-hazardous only)", "Specialized treatment", "Residual-waste pathway"].map((pathway, index) => <div key={pathway} className="flex items-center gap-4 rounded-2xl border border-white/10 bg-white/[.03] p-4"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-emerald-400/10 text-sm font-bold text-emerald-300">0{index + 1}</span><span className="text-sm text-slate-300">{pathway}</span><ChevronRight className="ml-auto text-slate-600" size={17} /></div>)}</div><div className="mt-6 rounded-2xl border border-amber-400/15 bg-amber-400/[.04] p-4 text-sm text-amber-200">A municipal worker must verify your physical deposit before points or a material batch can be created.</div><button onClick={() => setPage("overview")} className="mt-5 text-sm text-emerald-300">← Back to dashboard</button></Card></div><CollectionCenters centers={data.centers} demo={demoMode} /></div>;
}

function PointsPage({ data }) {
  const history = (data.scans || []).filter((scan) => scan.status === "VERIFIED");
  const leaderboard = data.profile?.leaderboard?.length ? data.profile.leaderboard : demoLeaderboard;
  return <div className="space-y-6"><div className="grid gap-5 md:grid-cols-3"><StatCard icon={Trophy} label="Current points" value={data.profile?.wallet?.greenPoints || 0} detail="Verified GreenPoints balance" /><StatCard icon={Leaf} label="Environmental impact" value={`${Number(data.profile?.impact?.verifiedWeightKg || 0).toFixed(1)} kg`} detail="Waste diverted from landfill" tone="sky" /><StatCard icon={Sparkles} label="Badges earned" value={data.profile?.badges?.length || 0} detail="Milestones unlocked" tone="amber" /></div><div className="grid gap-5 lg:grid-cols-[1fr_.8fr]"><Card className="p-6"><SectionTitle eyebrow="Ledger" title="Transaction history" />{history.length ? history.map((scan) => <div key={scan.scanId} className="flex items-center justify-between border-t border-white/5 py-4"><div><p className="font-medium">{scan.category}</p><p className="text-xs text-slate-500">{scan.verifiedWeight} kg · {new Date(scan.verifiedAt).toLocaleDateString()}</p></div><span className="font-semibold text-emerald-300">+{scan.greenPoints} pts</span></div>) : <EmptyState title="No verified transactions yet" description="Points are never awarded for an upload alone." />}</Card><Card className="p-6"><SectionTitle eyebrow="Community" title="Leaderboard" /><div className="space-y-2">{leaderboard.slice(0, 5).map((person, index) => <div key={person.userId || person.name} className="flex items-center gap-3 rounded-xl bg-white/[.03] p-3"><span className="w-6 text-center font-display font-bold text-emerald-300">{person.rank || index + 1}</span><div className="flex-1"><p className="text-sm font-medium">{person.name || person.userId}</p><p className="text-xs text-slate-500">{person.ward || "Community ranking"}</p></div><span className="text-sm font-semibold">{person.points || person.greenPoints} pts</span></div>)}</div></Card></div></div>;
}

function WorkerDashboard({ data, onVerify }) {
  const [centerId, setCenterId] = useState(""); const pending = (data.scans || []).filter((scan) => scan.status === "PENDING");
  return <div className="space-y-6"><div className="grid gap-5 md:grid-cols-3"><StatCard icon={ClipboardCheck} label="Pending verification" value={pending.length} detail="Live citizen deposits" tone="amber" /><StatCard icon={Truck} label="Centers online" value={data.centers?.length || "—"} detail="Configure centers to verify" tone="sky" /><StatCard icon={ShieldCheck} label="Trust rule" value="100%" detail="Human verification required" /></div><Card className="p-6"><SectionTitle eyebrow="Municipal operations" title="Verification queue" description="Scan the physical deposit, record weight, and unlock the next recovery step." /><input value={centerId} onChange={(event) => setCenterId(event.target.value)} placeholder="Collection center ID" className="mb-5 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm outline-none focus:border-emerald-400" /><div className="grid gap-4 lg:grid-cols-2">{pending.length ? pending.map((scan) => <VerifyItem key={scan.scanId} scan={scan} centerId={centerId} onVerify={onVerify} />) : <EmptyState title="Queue is clear" description="New citizen submissions will appear here from the live API." />}</div></Card></div>;
}

function WorkerBatches({ data, request, setNotice }) {
  const [selected, setSelected] = useState([]); const [quantity, setQuantity] = useState(""); const [centerId, setCenterId] = useState(""); const [qualityStatus, setQualityStatus] = useState("PENDING"); const [contaminationStatus, setContaminationStatus] = useState("UNKNOWN"); const [status, setStatus] = useState("AGGREGATING");
  const verified = (data.scans || []).filter((scan) => scan.status === "VERIFIED" && !scan.batchId);
  const updateBatch = async (batchId, nextStatus, current) => { try { await request(`/batches/${batchId}`, { method: "PATCH", body: JSON.stringify({ status: nextStatus, qualityStatus: current.qualityStatus, contaminationStatus: current.contaminationStatus }) }); setNotice({ type: "success", text: "Material batch status updated." }); } catch (error) { setNotice({ type: "error", text: error.message }); } };
  const create = async () => { try { await request("/batches", { method: "POST", body: JSON.stringify({ scanIds: selected, quantity: quantity || selected.length, centerId, qualityStatus, contaminationStatus, status }) }); setNotice({ type: "success", text: "Material batch created in DynamoDB." }); } catch (error) { setNotice({ type: "error", text: error.message }); } };
  return <div className="space-y-6"><Card className="p-6"><SectionTitle eyebrow="Aggregate" title="Material batches" description="Receive verified deposits, record quantity and quality, then prepare recovery routing." action={<button disabled={!selected.length} onClick={create} className="rounded-xl bg-emerald-400 px-4 py-2 text-xs font-bold text-[#071411] disabled:opacity-40">Create batch ({selected.length})</button>} /><div className="mb-5 grid gap-3 md:grid-cols-4"><input value={quantity} onChange={(event) => setQuantity(event.target.value)} type="number" min="1" placeholder="Quantity" className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm outline-none focus:border-emerald-400" /><input value={centerId} onChange={(event) => setCenterId(event.target.value)} placeholder="Collection center ID" className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm outline-none focus:border-emerald-400" /><select value={qualityStatus} onChange={(event) => setQualityStatus(event.target.value)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm"><option>PENDING</option><option>PASSED</option><option>ACCEPTABLE</option><option>FAILED</option></select><select value={contaminationStatus} onChange={(event) => setContaminationStatus(event.target.value)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm"><option>UNKNOWN</option><option>CLEAR</option><option>CONTAMINATED</option></select></div><div className="mb-5 flex flex-wrap gap-2">{["COLLECTING", "AGGREGATING", "QUALITY_CHECK"].map((value) => <button key={value} onClick={() => setStatus(value)} className={`rounded-lg px-3 py-2 text-xs ${status === value ? "bg-emerald-400/20 text-emerald-300" : "bg-white/5 text-slate-400"}`}>{value}</button>)}</div>{verified.length ? <div className="grid gap-3 md:grid-cols-2">{verified.map((scan) => <label key={scan.scanId} className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[.03] p-4"><input type="checkbox" checked={selected.includes(scan.scanId)} onChange={(event) => setSelected((items) => event.target.checked ? [...items, scan.scanId] : items.filter((id) => id !== scan.scanId))} /><div><p className="font-medium">{scan.category}</p><p className="text-xs text-slate-500">{scan.materialType} · {scan.verifiedWeight} kg</p></div></label>)}</div> : <EmptyState title="No unbatched verified deposits" />}</Card><Card className="p-6"><SectionTitle eyebrow="Material bank" title="Existing batches" />{data.batches?.length ? data.batches.map((batch) => <div key={batch.batchId} className="border-t border-white/5 py-4"><div className="flex items-center justify-between gap-3"><div><p className="font-medium">{batch.materialType} · {batch.quantity || batch.scanIds?.length || 0} units</p><p className="text-xs text-slate-500">{batch.weightKg} kg · centers: {(batch.sourceCollectionCenters || []).join(", ")} · quality {batch.qualityStatus || "PENDING"}</p></div><StatusBadge tone={["HIGH", "CRITICAL"].includes(batch.hazardLevel) ? "rose" : "emerald"}>{batch.workflowStatus}</StatusBadge></div><div className="mt-3 flex flex-wrap gap-2">{["QUALITY_CHECK", "READY_FOR_RECOVERY", "PARTNER_REQUESTED", "PICKUP_SCHEDULED", "RECOVERED", "REJECTED"].map((nextStatus) => <button key={nextStatus} onClick={() => updateBatch(batch.batchId, nextStatus, batch)} className="rounded-lg border border-white/10 px-2 py-1 text-[10px] text-slate-400 hover:border-emerald-400/40 hover:text-emerald-300">{nextStatus}</button>)}</div></div>) : <EmptyState title="No batches created yet" />}</Card></div>;
}

function OfficerDashboard({ data, request }) {
  const metrics = data.analytics || {}; return <div className="space-y-6"><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><StatCard icon={Truck} label="Total waste collected" value={`${Number(metrics.totalWasteDivertedKg || 0).toFixed(1)} kg`} detail="Verified material batches" /><StatCard icon={Recycle} label="Recyclable material" value={`${(data.inventory || []).filter((x) => x.materialType !== "HAZARDOUS").length}`} detail="Active material streams" tone="sky" /><StatCard icon={AlertTriangle} label="Hazardous events" value={metrics.hazardousIncidents || 0} detail="SNS alert eligible" tone="rose" /><StatCard icon={PackageCheck} label="Recovery-ready batches" value={metrics.availableBatches || 0} detail="Available for matching" tone="amber" /></div><div className="grid gap-5 lg:grid-cols-[1.1fr_.9fr]"><Card className="p-6"><SectionTitle eyebrow="Operations" title="Ward statistics" description="Ward-level planning data is mock-only until the backend adds ward dimensions." /><div className="space-y-4">{demoWardStats.map((ward) => <div key={ward.ward}><div className="mb-2 flex justify-between text-sm"><span>{ward.ward}</span><span className="text-emerald-300">{ward.diverted} kg</span></div><div className="h-2 rounded-full bg-white/5"><div style={{ width: `${Math.round(ward.diverted / 2000 * 100)}%` }} className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-400" /></div><p className="mt-1 text-xs text-slate-600">{ward.households} participating households · demo planning data</p></div>)}</div></Card><Card className="p-6"><SectionTitle eyebrow="AI Copilot" title="Recommended action" /><div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[.04] p-5"><Bot className="mb-4 text-emerald-300" size={24} /><p className="text-sm leading-6 text-slate-300">Prioritise a battery and pesticide-container collection drive in wards with low verified hazardous returns. Final campaign recommendations should be reviewed by an officer.</p><button onClick={() => request("/analytics")} className="mt-5 rounded-xl border border-emerald-400/30 px-3 py-2 text-xs text-emerald-300">Refresh live metrics</button></div></Card></div><InventoryPage data={data} /></div>;
}

function InventoryPage({ data }) { return <div className="space-y-5"><ImpactCards analytics={data.analytics} demo={isDemoMode} /><MaterialBank inventory={data.inventory} batches={data.batches} demo={isDemoMode} /><NotificationCenter demo={isDemoMode} /></div>; }

function PublicProjects({ data, request, setNotice }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [materialType, setMaterialType] = useState("PET");
  const [quantity, setQuantity] = useState("10");
  const create = async () => {
    try {
      await request("/projects", { method: "POST", body: JSON.stringify({
        name, description, materialRequirements: [{ materialType, estimatedQuantity: quantity, estimatedWeightKg: 0 }],
      }) });
      setNotice({ type: "success", text: "Project created and queued for approval." });
    } catch (error) { setNotice({ type: "error", text: error.message }); }
  };
  const decide = async (projectId, decision) => {
    try {
      await request(`/projects/${projectId}/approval`, { method: "POST", body: JSON.stringify({ decision }) });
      setNotice({ type: "success", text: `Project ${decision.toLowerCase()}.` });
    } catch (error) { setNotice({ type: "error", text: error.message }); }
  };
  const complete = async (projectId) => {
    try {
      await request(`/projects/${projectId}`, { method: "PATCH", body: JSON.stringify({ status: "COMPLETED" }) });
      setNotice({ type: "success", text: "Project marked completed and QR information is now public." });
    } catch (error) { setNotice({ type: "error", text: error.message }); }
  };
  return <div className="space-y-6"><Card className="p-6"><SectionTitle eyebrow="Circular projects" title="Public-space installations" description="Create and approve only non-hazardous, uncontaminated, quality-cleared project materials." /><div className="grid gap-3 md:grid-cols-4"><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Project name" className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm" /><input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm" /><select value={materialType} onChange={(event) => setMaterialType(event.target.value)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm"><option>PET</option><option>HDPE</option><option>ALUMINUM</option><option>STEEL</option><option>PAPER</option><option>CARDBOARD</option></select><div className="flex gap-2"><input value={quantity} onChange={(event) => setQuantity(event.target.value)} type="number" min="1" className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm" /><button onClick={create} className="rounded-xl bg-emerald-400 px-4 py-3 text-sm font-bold text-[#071411]">Create</button></div></div></Card><Card className="p-6"><SectionTitle eyebrow="Approval workflow" title="Project records" />{data.projects?.length ? data.projects.map((project) => <div key={project.projectId} className="border-t border-white/5 py-4"><div className="flex justify-between gap-3"><div><p className="font-medium">{project.name}</p><p className="text-xs text-slate-500">{project.description}</p><p className="mt-2 text-xs text-slate-500">{project.materialRequirements?.map((item) => `${item.materialType} · ${item.estimatedQuantity} units`).join(", ")}</p><p className="mt-2 text-xs text-slate-500">Diverted: {project.impactMetrics?.amountDivertedKg || 0} kg</p></div><StatusBadge tone={project.approvalStatus === "APPROVED" ? "emerald" : project.approvalStatus === "REJECTED" ? "rose" : "amber"}>{project.status}</StatusBadge></div>{project.approvalStatus === "PENDING" && <div className="mt-3 flex gap-2"><button onClick={() => decide(project.projectId, "APPROVED")} className="rounded-lg bg-emerald-400/15 px-3 py-2 text-xs text-emerald-300">Approve</button><button onClick={() => decide(project.projectId, "REJECTED")} className="rounded-lg bg-rose-400/15 px-3 py-2 text-xs text-rose-300">Reject</button></div>}{project.status === "MATERIAL_ALLOCATED" && <button onClick={() => complete(project.projectId)} className="mt-3 rounded-lg bg-emerald-400/15 px-3 py-2 text-xs text-emerald-300">Mark completed</button>}{project.status === "COMPLETED" && <p className="mt-3 text-xs text-emerald-300">QR: /public-projects/{project.qrToken}</p>}</div>) : <EmptyState title="No public projects yet" description="Create a project proposal to begin." />}</Card></div>;
}

function PartnerDashboard({ data, request, setNotice }) { const [name, setName] = useState(""); const [materials, setMaterials] = useState("PLASTIC, PAPER"); const [partnerType, setPartnerType] = useState("RECYCLER"); const [minimumQuantity, setMinimumQuantity] = useState("0"); const save = async () => { try { await request("/partners/me", { method: "PUT", body: JSON.stringify({ name, partnerType, minimumQuantity, acceptedMaterials: materials.split(",").map((x) => x.trim()).filter(Boolean) }) }); setNotice({ type: "success", text: "Recovery profile saved. Verification is required before matching." }); } catch (error) { setNotice({ type: "error", text: error.message }); } }; return <div className="space-y-6"><Card className="p-6"><SectionTitle eyebrow="Organisation profile" title="Define your recovery lane" description="Accepted materials power live matching. Hazardous materials always require specialised treatment." /><div className="grid gap-3 md:grid-cols-4"><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Organisation name" className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm outline-none focus:border-emerald-400" /><select value={partnerType} onChange={(event) => setPartnerType(event.target.value)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm"><option>RECYCLER</option><option>REUSE_PARTNER</option><option>UPCYCLER</option><option>ORIGINAL_PRODUCER</option><option>COMMUNITY_PROJECT</option><option>SPECIALIZED_TREATMENT</option></select><input value={materials} onChange={(event) => setMaterials(event.target.value)} placeholder="PLASTIC, PAPER, GLASS" className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm outline-none focus:border-emerald-400" /><div className="flex gap-2"><input value={minimumQuantity} onChange={(event) => setMinimumQuantity(event.target.value)} type="number" min="0" placeholder="Min quantity" className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm" /><button onClick={save} className="rounded-xl bg-emerald-400 px-4 py-3 text-sm font-bold text-[#071411]">Save</button></div></div></Card><Card className="p-6"><SectionTitle eyebrow="Live matching" title="Available recovery batches" />{data.matches?.length ? data.matches.map((match) => <div key={match.matchId} className="flex flex-col gap-3 border-t border-white/5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-medium">{match.materialType} · {match.weightKg} kg</p><p className="text-xs text-slate-500">{match.partnerName} · {match.pathway} · priority {match.priority}</p><p className="mt-1 text-xs text-slate-500">{match.reason}</p></div><button onClick={async () => { try { await request(`/matches/${match.matchId}/accept`, { method: "POST", body: "{}" }); setNotice({ type: "success", text: "Recovery request accepted." }); } catch (error) { setNotice({ type: "error", text: error.message }); } }} className="rounded-xl border border-emerald-400/30 px-3 py-2 text-xs text-emerald-300">Request recovery</button></div>) : <EmptyState title="No eligible batches" description="Only verified partners with compatible, quality-checked batches appear here." />}</Card></div>; }

function RecoveryHistory() { return <Card className="p-6"><SectionTitle eyebrow="Outcomes" title="Recovery history" description="Demo-only until the recovery outcome API is implemented." />{demoRecoveryHistory.map((item) => <div key={item.id} className="flex items-center justify-between border-t border-white/5 py-4"><div><p className="font-medium">{item.material}</p><p className="text-xs text-slate-500">{item.partner} · {item.date}</p></div><StatusBadge tone={item.status === "Recovered" ? "emerald" : "amber"}>{item.status}</StatusBadge></div>)}</Card>; }

function ChatPage({ request }) { const [message, setMessage] = useState(""); const [imageData, setImageData] = useState(""); const [messages, setMessages] = useState([]); const [busy, setBusy] = useState(false); const send = async () => { if (!message.trim() && !imageData) return; setBusy(true); const question = message; setMessages((items) => [...items, { from: "user", text: question || "Image question" }]); try { const result = await request("/chat", { method: "POST", body: JSON.stringify({ message, imageData: imageData || undefined }) }); setMessages((items) => [...items, { from: "ai", text: result.answer }]); setMessage(""); setImageData(""); } catch (error) { setMessages((items) => [...items, { from: "ai", text: error.message }]); } finally { setBusy(false); } }; return <Card className="mx-auto max-w-3xl overflow-hidden"><div className="border-b border-white/5 p-6"><div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-400/10 text-emerald-300"><Bot size={23} /></span><div><h2 className="font-display text-xl font-semibold">KasaMukti AI assistant</h2><p className="text-xs text-slate-500">Role-aware · live platform context · verified safety guidance</p></div></div></div><div className="min-h-80 space-y-4 p-6">{messages.length ? messages.map((item, index) => <div key={`${item.from}-${index}`} className={`flex ${item.from === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${item.from === "user" ? "bg-emerald-400 text-[#071411]" : "bg-white/[.05] text-slate-300"}`}>{item.text}</div></div>) : <div className="flex h-64 flex-col items-center justify-center text-center"><Bot className="mb-4 text-emerald-300" size={34} /><p className="font-medium">What are you recovering today?</p><p className="mt-2 max-w-sm text-sm text-slate-500">Ask about a material, your points, or a safe collection route.</p></div>}</div><div className="border-t border-white/5 p-4"><div className="mb-3 flex items-center gap-2"><label className="cursor-pointer rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-400 hover:text-white"><Camera size={14} className="mr-1 inline" /> Add image<input type="file" accept="image/*" className="hidden" onChange={(event) => { const reader = new FileReader(); reader.onload = () => setImageData(reader.result); reader.readAsDataURL(event.target.files[0]); }} /></label>{imageData && <span className="text-xs text-emerald-300">Image attached</span>}</div><div className="flex gap-2"><input value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => event.key === "Enter" && send()} placeholder="Ask KasaMukti AI…" className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none focus:border-emerald-400" /><button disabled={busy} onClick={send} className="rounded-xl bg-emerald-400 px-4 text-[#071411] disabled:opacity-50">{busy ? <LoaderCircle className="animate-spin" size={18} /> : <Send size={18} />}</button></div></div></Card>; }

function AssistantPage({ request }) {
  const { language, t } = useTranslation();
  const [message, setMessage] = useState("");
  const [imageData, setImageData] = useState("");
  const [messages, setMessages] = useState([]);
  const [lastRequest, setLastRequest] = useState(null);
  const [busy, setBusy] = useState(false);
  const [conversationId] = useState(() => localStorage.getItem("kasamukti-chat") || crypto.randomUUID());
  useEffect(() => localStorage.setItem("kasamukti-chat", conversationId), [conversationId]);
  const send = async (retryRequest = null) => {
    const payload = retryRequest || { message: message.trim(), imageData: imageData || undefined };
    if (!payload.message && !payload.imageData) return;
    setBusy(true);
    if (!retryRequest) {
      setMessages((items) => [...items, { from: "user", text: payload.message || "Image question", image: Boolean(payload.imageData) }]);
      setLastRequest(payload);
    }
    try {
      const result = await request("/chat", { method: "POST", body: JSON.stringify({ ...payload, conversationId, language }) });
      setMessages((items) => [...items, { from: "ai", text: result.answer, metadata: result.contextMetadata, sources: result.sources, confidence: result.confidence }]);
      if (!retryRequest) { setMessage(""); setImageData(""); }
    } catch (error) {
      setMessages((items) => [...items, { from: "error", text: error.message, retry: payload }]);
    } finally { setBusy(false); }
  };
  return <Card className="mx-auto max-w-3xl overflow-hidden"><div className="border-b border-white/5 p-6"><div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-400/10 text-emerald-300"><Bot size={23} /></span><div><h2 className="font-display text-xl font-semibold">{t("navigation.askAi")}</h2><p className="text-xs text-slate-500">Role-aware · retrieved live context · verified safety knowledge</p></div></div></div><div className="min-h-80 space-y-4 p-6">{messages.length ? messages.map((item, index) => <div key={`${item.from}-${index}`} className={`flex ${item.from === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-6 ${item.from === "user" ? "bg-emerald-400 text-[#071411]" : item.from === "error" ? "border border-rose-400/20 bg-rose-400/10 text-rose-200" : "bg-white/[.05] text-slate-300"}`}><p>{item.text}</p>{item.from === "error" && <button onClick={() => send(item.retry)} className="mt-3 rounded-lg border border-rose-300/30 px-3 py-1.5 text-xs font-semibold">Retry</button>}{item.from === "ai" && <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-slate-500"><span>confidence {Math.round((item.confidence || 0) * 100)}%</span>{item.metadata?.imageAnalyzed && <span>image analyzed</span>}{item.sources?.slice(0, 3).map((source) => <span key={source.id} className="rounded bg-white/5 px-2 py-1">{source.id}</span>)}</div>}</div></div>) : <div className="flex h-64 flex-col items-center justify-center text-center"><Bot className="mb-4 text-emerald-300" size={34} /><p className="font-medium">What are you recovering today?</p><p className="mt-2 max-w-sm text-slate-500">Ask about a material, your points, a collection route, or a live recovery batch.</p></div>}</div><div className="border-t border-white/5 p-4"><div className="mb-3 flex items-center gap-2"><label className="cursor-pointer rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-400 hover:text-white"><Camera size={14} className="mr-1 inline" /> Add image<input type="file" accept="image/*" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (!file) return; const reader = new FileReader(); reader.onload = () => setImageData(reader.result); reader.readAsDataURL(file); }} /></label>{imageData && <span className="text-xs text-emerald-300">Image attached</span>}<span className="ml-auto text-[10px] text-slate-600">Conversation saved for this device</span></div><div className="flex gap-2"><input value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => event.key === "Enter" && send()} placeholder="Ask KasaMukti AI…" className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none focus:border-emerald-400" /><button disabled={busy} onClick={() => send()} className="rounded-xl bg-emerald-400 px-4 text-[#071411] disabled:opacity-50">{busy ? <LoaderCircle className="animate-spin" size={18} /> : <Send size={18} />}</button></div></div></Card>;
}

function VerifyItem({ scan, centerId, onVerify }) { const [weight, setWeight] = useState(""); const [busy, setBusy] = useState(false); return <div className="rounded-2xl border border-white/10 bg-white/[.03] p-5"><div className="flex items-start justify-between"><div><p className="font-semibold">{scan.category}</p><p className="mt-1 text-xs text-slate-500">{scan.materialType} · {scan.scanId.slice(0, 8)}</p></div><StatusBadge tone={["HIGH", "CRITICAL"].includes(scan.hazardLevel) ? "rose" : ["MEDIUM", "MODERATE"].includes(scan.hazardLevel) ? "amber" : "emerald"}>{scan.hazardLevel}</StatusBadge></div><div className="mt-5 flex gap-2"><input type="number" min="0.01" step="0.01" value={weight} onChange={(event) => setWeight(event.target.value)} placeholder="Weight kg" className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/10 px-3 py-2 text-sm outline-none focus:border-emerald-400" /><button disabled={!centerId || !weight || busy} onClick={async () => { setBusy(true); try { await onVerify(scan.scanId, weight, centerId); } finally { setBusy(false); } }} className="rounded-xl bg-emerald-400 px-3 py-2 text-xs font-bold text-[#071411] disabled:opacity-40">{busy ? <LoaderCircle size={15} className="animate-spin" /> : "Verify deposit"}</button></div></div>; }
function Contribution({ scan }) { return <div className="flex items-center justify-between border-t border-white/5 py-4"><div><p className="font-medium">{scan.category}</p><p className="text-xs text-slate-500">{scan.materialType} · {new Date(scan.createdAt).toLocaleDateString()}</p></div><StatusBadge tone={scan.status === "VERIFIED" ? "emerald" : "amber"}>{scan.status}</StatusBadge></div>; }
function MiniMetric({ value, label }) { return <div className="rounded-2xl bg-white/[.04] p-3"><p className="font-display text-xl font-semibold">{value}</p><p className="mt-1 text-xs text-slate-500">{label}</p></div>; }
function ActionTile({ icon: Icon, title, description, onClick }) { return <button onClick={onClick} className="glass group rounded-3xl p-5 text-left transition hover:-translate-y-1 hover:border-emerald-400/30"><Icon className="mb-8 text-emerald-300" size={22} /><p className="font-display text-lg font-semibold">{title}</p><p className="mt-1 text-sm text-slate-500">{description}</p><ChevronRight className="mt-4 text-slate-600 transition group-hover:translate-x-1 group-hover:text-emerald-300" size={18} /></button>; }
