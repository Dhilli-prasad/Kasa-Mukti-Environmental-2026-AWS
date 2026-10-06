import { motion } from "framer-motion";
import { ArrowUpRight, Inbox } from "lucide-react";

export function Card({ children, className = "", ...props }) {
  return <div className={`glass rounded-3xl ${className}`} {...props}>{children}</div>;
}

export function SectionTitle({ eyebrow, title, description, action }) {
  return <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
    <div>
      {eyebrow && <p className="mb-2 text-xs font-semibold uppercase tracking-[.22em] text-emerald-300">{eyebrow}</p>}
      <h2 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">{title}</h2>
      {description && <p className="mt-2 max-w-2xl text-sm text-slate-400">{description}</p>}
    </div>
    {action}
  </div>;
}

export function StatCard({ icon: Icon, label, value, detail, tone = "emerald" }) {
  const tones = {
    emerald: "bg-emerald-400/10 text-emerald-300",
    amber: "bg-amber-400/10 text-amber-300",
    rose: "bg-rose-400/10 text-rose-300",
    sky: "bg-sky-400/10 text-sky-300"
  };
  return <motion.div layout className="glass rounded-3xl p-5">
    <div className={`mb-7 flex h-10 w-10 items-center justify-center rounded-2xl ${tones[tone]}`}><Icon size={20} /></div>
    <p className="text-sm text-slate-400">{label}</p>
    <p className="mt-1 font-display text-3xl font-semibold">{value}</p>
    <p className="mt-2 text-xs text-slate-500">{detail}</p>
  </motion.div>;
}

export function StatusBadge({ children, tone = "emerald" }) {
  const tones = { emerald: "bg-emerald-400/10 text-emerald-300", amber: "bg-amber-400/10 text-amber-300", rose: "bg-rose-400/10 text-rose-300", sky: "bg-sky-400/10 text-sky-300" };
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${tones[tone]}`}>{children}</span>;
}

export function EmptyState({ title = "Nothing here yet", description = "Live AWS data will appear here when available." }) {
  return <div className="flex min-h-32 flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 p-6 text-center"><Inbox className="mb-2 text-slate-600" size={24} /><p className="text-sm font-medium text-slate-400">{title}</p><p className="mt-1 text-xs text-slate-600">{description}</p></div>;
}

export function LinkButton({ children, onClick }) {
  return <button onClick={onClick} className="flex items-center gap-1 text-sm font-semibold text-emerald-300 hover:text-emerald-200">{children}<ArrowUpRight size={15} /></button>;
}
