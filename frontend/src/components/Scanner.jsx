import { useRef, useState } from "react";
import { Camera, CheckCircle2, FileImage, LoaderCircle, MapPin, Mic2, ScanLine, UploadCloud, X } from "lucide-react";
import { motion } from "framer-motion";
import { useTranslation } from "../lib/i18n";
import { apiRequest } from "../lib/api";
import { isDemoMode } from "../lib/config";

const DEMO_PREVIEW = `data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 620"><defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#102d25"/><stop offset="1" stop-color="#28735b"/></linearGradient></defs><rect width="900" height="620" fill="url(#g)"/><circle cx="760" cy="90" r="150" fill="#9be15d" opacity=".16"/><path d="M390 485c-34-80-30-222 20-295 22-32 72-36 98-5 48 56 68 179 40 300z" fill="#e9efe3"/><path d="M456 208h70l-8 46h-54z" fill="#f0b94f"/><path d="M449 258h85v190c-20 38-65 38-85 0z" fill="#edf4ea"/><path d="M449 305h85v70h-85z" fill="#e8aa3d"/><text x="32" y="570" fill="#d8f7df" font-family="sans-serif" font-size="26" font-weight="700">WARD 12 · SAFE RETURN DEMO</text></svg>`)}`;

const DEMO_RESULT = {
  category: "agricultural-container",
  materialType: "HDPE",
  manufacturer: "AgroShield",
  productName: "CropGuard 50 EC",
  hazardLevel: "CRITICAL",
  confidence: 0.94,
  recommendedPathway: "SPECIALIZED_TREATMENT",
  requiresManualVerification: true,
  disposal_instructions: {
    English: "Keep the container sealed. Do not burn, open, wash, or reuse it. Deliver it to an authorised hazardous-waste collection centre."
  }
};

export default function Scanner({ citizenId, onAnalyzed, demoMode = isDemoMode }) {
  const { language, t } = useTranslation();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(demoMode ? DEMO_PREVIEW : "");
  const [result, setResult] = useState(demoMode ? DEMO_RESULT : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const choose = (selected) => {
    const next = selected?.[0];
    if (!next || !next.type.startsWith("image/")) {
      setError("Choose a valid image file.");
      return;
    }
    setFile(next);
    setResult(null);
    setError("");
    setPreview(URL.createObjectURL(next));
  };

  const analyze = async () => {
    if (!file) return;

    setBusy(true);
    setError("");

    try {
      if (demoMode) {
        setResult(DEMO_RESULT);
        onAnalyzed?.(DEMO_RESULT);
        return;
      }

      const imageData = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error("Could not read image"));
        reader.readAsDataURL(file);
      });

      const payload = await apiRequest("/waste/analyze", {
        role: "CITIZEN",
        userId: citizenId,
        method: "POST",
        body: JSON.stringify({
          imageData,
          citizenId,
          language
        })
      });

      const scan = payload.scan || payload;
      setResult(scan);
      onAnalyzed?.(scan);
    } catch (requestError) {
      setError(requestError.message || "Unable to analyze the waste image.");
    } finally {
      setBusy(false);
    }
  };

  const speak = () => {
    if (!result?.disposal_instructions || !("speechSynthesis" in window)) {
      setError(t("waste.speechUnavailable"));
      return;
    }

    window.speechSynthesis.cancel();
    const instruction =
      result.disposal_instructions[language] ||
      result.disposal_instructions.English;

    window.speechSynthesis.speak(new SpeechSynthesisUtterance(instruction));
  };

  return <section className="glass rounded-3xl p-6"><div className="mb-5 flex items-start justify-between"><div><p className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[.2em] text-emerald-300"><ScanLine size={14} /> {demoMode ? t("waste.simulatedVision") : t("waste.vision")}</p><h2 className="font-display text-2xl font-semibold">{t("waste.analyze")}</h2><p className="mt-2 text-sm text-slate-400">{demoMode ? t("waste.demoResult") : t("waste.liveResult")}</p></div><div className="rounded-xl bg-emerald-400/10 p-2 text-emerald-300"><Camera size={20} /></div></div>
    {!preview ? <button onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); choose(event.dataTransfer.files); }} className="group flex min-h-72 w-full flex-col items-center justify-center rounded-2xl border border-dashed border-emerald-300/25 bg-emerald-400/[.03] p-6 text-center transition hover:border-emerald-300/60 hover:bg-emerald-400/[.07]"><UploadCloud className="mb-4 text-emerald-300 transition group-hover:-translate-y-1" size={34} /><p className="font-semibold">Drop an image here</p><p className="mt-2 text-sm text-slate-500">or tap to browse · camera-ready on mobile</p></button> : <div className="relative overflow-hidden rounded-2xl"><img src={preview} alt="Waste preview" className="max-h-80 w-full object-cover" />{busy && <motion.div initial={{ top: 0 }} animate={{ top:"100%" }} transition={{ repeat: Infinity, duration: 1.8, ease: "linear" }} className="absolute left-0 h-1 w-full bg-emerald-300 shadow-[0_0_20px_5px_rgba(110,231,183,.7)]" />}<button onClick={() => { setFile(null); setPreview(""); setResult(null); }} className="absolute right-3 top-3 rounded-full bg-black/60 p-2 text-white"><X size={16} /></button></div>}
    <input ref={inputRef} type="file" accept="image/*" capture="environment" onChange={(event) => choose(event.target.files)} className="hidden" />
    {preview && !result && <button disabled={busy} onClick={analyze} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-400 py-3 text-sm font-bold text-[#071411] disabled:opacity-50">{busy ? <><LoaderCircle size={17} className="animate-spin" /> Calling Amazon Bedrock…</> : <><FileImage size={17} /> Identify with AI</>}</button>}
    {error && <p className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-300">{error}</p>}
    {result && <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-5 rounded-2xl border border-emerald-300/20 bg-emerald-400/[.06] p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-[.2em] text-slate-500">Classification result</p><h3 className="mt-1 font-display text-2xl font-bold">{result.category}</h3><p className="mt-1 text-sm text-slate-400">{result.materialType}</p></div><span className={`rounded-full px-3 py-1 text-xs font-bold ${["HIGH", "CRITICAL"].includes(result.hazardLevel) ? "bg-rose-400/15 text-rose-300" : result.hazardLevel === "MEDIUM" || result.hazardLevel === "MODERATE" ? "bg-amber-400/15 text-amber-300" : "bg-emerald-400/15 text-emerald-300"}`}>{result.hazardLevel} risk</span></div>{demoMode && <div className="mt-3 rounded-xl border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-xs text-amber-100">Simulated AI response for presentation · no points awarded by this screen.</div>}<div className="mt-5 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-black/20 p-3"><p className="text-[10px] uppercase tracking-wider text-slate-500">Confidence</p><p className="mt-1 text-lg font-semibold">{result.confidence ? `${Math.round(Number(result.confidence) * 100)}%` : "Review required"}</p></div><div className="rounded-xl bg-black/20 p-3"><p className="text-[10px] uppercase tracking-wider text-slate-500">Product</p><p className="mt-1 truncate text-sm font-semibold">{result.productName || "Not detected"}</p></div><div className="rounded-xl bg-black/20 p-3"><p className="text-[10px] uppercase tracking-wider text-slate-500">Manufacturer</p><p className="mt-1 truncate text-sm font-semibold">{result.manufacturer || "Not detected"}</p></div></div><div className="mt-3 rounded-xl bg-black/20 p-4"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Recommended recovery pathway</p><div className="mt-2 flex flex-wrap gap-2"><span className="rounded-lg bg-emerald-400/10 px-2.5 py-1.5 text-xs text-emerald-200">{String(result.recommendedPathway || result.recoveryOptions?.[0] || "Human review").replaceAll("_", " ")}</span></div></div><div className="mt-3 rounded-xl bg-black/20 p-4"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Verified guidance · English</p><p className="mt-2 text-sm leading-6 text-slate-300">{result.disposal_instructions?.English}</p><div className="mt-3 flex flex-wrap gap-2"><button onClick={speak} className="flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-300 hover:border-emerald-300/40"><Mic2 size={14} /> Listen to instructions</button><span className="flex items-center gap-1 rounded-lg bg-amber-400/10 px-3 py-2 text-xs text-amber-300"><CheckCircle2 size={14} /> {result.requiresManualVerification ? "Manual verification required" : "Awaiting verification"}</span></div></div><button onClick={() => document.getElementById("centers")?.scrollIntoView({ behavior: "smooth" })} className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-300/25 py-3 text-sm font-semibold text-emerald-200 hover:bg-emerald-400/10">Find a collection center <MapPin size={16} /></button></motion.div>}
  </section>;
}
