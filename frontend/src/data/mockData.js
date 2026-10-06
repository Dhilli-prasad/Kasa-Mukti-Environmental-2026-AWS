// Demo-only data for platform surfaces that do not have a backend route yet.
// Real API responses always take precedence in App.jsx.
export const demoLeaderboard = [
  { rank: 1, name: "Aarav S.", points: 2840, ward: "Ward 14" },
  { rank: 2, name: "Meera K.", points: 2310, ward: "Ward 7" },
  { rank: 3, name: "You", points: 0, ward: "Ward 12" }
];

export const demoWardStats = [
  { ward: "Ward 7", diverted: 1840, households: 412 },
  { ward: "Ward 12", diverted: 1260, households: 289 },
  { ward: "Ward 14", diverted: 980, households: 221 }
];

export const demoRecoveryHistory = [
  { id: "RH-104", material: "PET Plastic", partner: "GreenLoop Recycler", status: "Recovered", date: "12 Sep 2026" },
  { id: "RH-098", material: "Cardboard", partner: "PaperCycle Co.", status: "In transit", date: "05 Sep 2026" }
];

export const demoSteps = [
  { role: "CITIZEN", page: "overview", label: "Citizen spots waste", detail: "A used pesticide container is found near Ward 12." },
  { role: "CITIZEN", page: "scan", label: "Scan the item", detail: "The camera sends an image for Bedrock Vision analysis." },
  { role: "CITIZEN", page: "scan", label: "AI identifies risk", detail: "Agricultural chemical container · CRITICAL risk · manual verification." },
  { role: "CITIZEN", page: "overview", label: "Find a safe center", detail: "The nearest authorized hazardous-waste collection point is highlighted." },
  { role: "CITIZEN", page: "overview", label: "Deposit the item", detail: "The citizen hands the sealed container to a collection-center worker." },
  { role: "MUNICIPAL_WORKER", page: "overview", label: "Worker verifies", detail: "Physical deposit and 1.2 kg weight are confirmed." },
  { role: "CITIZEN", page: "points", label: "GreenPoints unlock", detail: "120 points are awarded only after verification." },
  { role: "MUNICIPAL_OFFICER", page: "inventory", label: "Material enters the bank", detail: "The verified stream is visible in municipal inventory." },
  { role: "MUNICIPAL_OFFICER", page: "inventory", label: "Create recovery batch", detail: "Batch KM-BATCH-042 is quality-checked and ready for routing." },
  { role: "MUNICIPAL_OFFICER", page: "chat", label: "Ask AI Copilot", detail: "The officer asks which verified pathway can accept the batch." },
  { role: "MUNICIPAL_OFFICER", page: "overview", label: "Show impact", detail: "Diversion, safety, and circular recovery outcomes are visible." }
];

export const demoSeedData = {
  scans: [{
    scanId: "KM-SCAN-042",
    citizenId: "demo-citizen",
    category: "agricultural-container",
    materialType: "HDPE",
    manufacturer: "AgroShield",
    productName: "CropGuard 50 EC",
    hazardLevel: "CRITICAL",
    confidence: 0.94,
    status: "PENDING",
    requiresManualVerification: true,
    createdAt: "2026-10-05T08:42:00+05:30",
    disposal_instructions: {
      English: "Keep the container sealed. Do not burn, open, wash, or reuse it. Deliver it to an authorised hazardous-waste collection centre.",
      Telugu: "కంటైనర్‌ను మూసివేసి ఉంచండి. కాల్చవద్దు, తెరవవద్దు, కడగవద్దు లేదా తిరిగి ఉపయోగించవద్దు. అధీకృత ప్రమాదకర వ్యర్థాల కేంద్రానికి ఇవ్వండి.",
      Hindi: "कंटेनर को बंद रखें। इसे जलाएं, खोलें, धोएं या दोबारा इस्तेमाल न करें। अधिकृत खतरनाक कचरा केंद्र में जमा करें।"
    }
  }],
  pending: [],
  inventory: [],
  batches: [],
  centers: [
    { centerId: "WARD12-CENTER", name: "Ward 12 Safe Recovery Hub", address: "Kothapet Community Hall", distance: "1.8 km", latitude: 17.385, longitude: 78.486, openingHours: "Today · 08:00–18:00", acceptedMaterials: ["HDPE", "SPECIAL WASTE"], acceptsHazardousWaste: true, acceptsAgriculturalWaste: true, status: "OPEN", currentUtilization: 42, verificationStatus: "VERIFIED" },
    { centerId: "WARD7-CENTER", name: "GreenLoop Materials Depot", address: "Lakshmi Nagar Market", distance: "4.2 km", latitude: 17.405, longitude: 78.475, openingHours: "Today · 09:00–17:00", acceptedMaterials: ["PET", "HDPE", "PAPER"], acceptsHazardousWaste: false, acceptsAgriculturalWaste: false, status: "OPEN", currentUtilization: 68, verificationStatus: "VERIFIED" }
  ],
  matches: [{ matchId: "KM-MATCH-PET-01", batchId: "KM-PET-00124", partnerName: "GreenLoop Recycler", materialType: "PET", weightKg: 850, pathway: "RECYCLING", priority: "HIGH", reason: "PET accepted · quantity and quality requirements satisfied", status: "ELIGIBLE", score: 94 }],
  projects: [],
  profile: {
    wallet: { greenPoints: 0 },
    impact: { verifiedWeightKg: 0, verifiedDeposits: 0 },
    badges: [],
    leaderboard: [{ rank: 3, name: "You", userId: "demo-citizen", points: 0, ward: "Ward 12" }]
  },
  analytics: { totalWasteDivertedKg: 184.6, totalScans: 38, verifiedDeposits: 31, hazardousIncidents: 4, availableBatches: 18, recoveredWeightKg: 2.8, activeCitizens: 684, activeRecoveryPartners: 12 },
  notifications: [{ notificationId: "DEMO-N-01", type: "GREENPOINTS_EARNED", message: "25 GreenPoints awarded", unread: true }, { notificationId: "DEMO-N-02", type: "RECOVERY_READY", message: "PET batch KM-PET-00124 is ready", unread: true }],
  demoMeta: { lastAction: "Ready for the live presentation", simulated: true }
};
