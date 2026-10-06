import { accessToken } from "./auth";
import { apiBaseUrl, isDemoMode } from "./config";

export function hasApi() {
  return Boolean(apiBaseUrl);
}

export async function apiRequest(path, { role, userId, ...options } = {}) {
  if (isDemoMode && path === "/chat") {
    const body = options.body ? JSON.parse(options.body) : {};
    const language = body.language || "en";
    const demoAnswers = {
      en: { image: "This demo image shows a potentially hazardous waste item. Keep it sealed and take it to an authorised collection centre. A municipal worker must verify the physical deposit before any GreenPoints are awarded.", text: "In demo mode, KasaMukti provides safety guidance from the presentation dataset. Ask about a material, collection route, or the verification step." },
      te: { image: "ఈ డెమో చిత్రంలో ప్రమాదకరమైన వ్యర్థం ఉండవచ్చు. దాన్ని మూసివేసి అధీకృత సేకరణ కేంద్రానికి తీసుకెళ్లండి. గ్రీన్ పాయింట్లకు ముందు మున్సిపల్ కార్మికుడు భౌతికంగా ధృవీకరించాలి.", text: "డెమో మోడ్‌లో కసముక్తి ప్రదర్శన డేటా నుంచి భద్రతా మార్గదర్శకత్వాన్ని అందిస్తుంది. పదార్థం, సేకరణ మార్గం లేదా ధృవీకరణ గురించి అడగండి." },
      hi: { image: "इस डेमो चित्र में संभावित खतरनाक कचरा दिखता है। इसे बंद रखें और अधिकृत संग्रह केंद्र ले जाएँ। ग्रीनपॉइंट्स से पहले नगरपालिका कर्मचारी को भौतिक सत्यापन करना होगा।", text: "डेमो मोड में कसमुक्ति प्रस्तुति डेटा से सुरक्षा मार्गदर्शन देती है। सामग्री, संग्रह मार्ग या सत्यापन के बारे में पूछें।" },
      ta: { image: "இந்த டெமோ படத்தில் அபாயகரமான கழிவு இருக்கலாம். அதை மூடி வைத்து அங்கீகரிக்கப்பட்ட சேகரிப்பு மையத்துக்கு எடுத்துச் செல்லுங்கள். கிரீன்பாயிண்ட்ஸ் வழங்குவதற்கு முன் நகராட்சி பணியாளர் சரிபார்க்க வேண்டும்.", text: "டெமோ முறையில் கசமுக்தி விளக்கத் தரவிலிருந்து பாதுகாப்பு வழிகாட்டுதலை வழங்குகிறது. பொருள், சேகரிப்பு வழி அல்லது சரிபார்ப்பு பற்றி கேளுங்கள்." },
      kn: { image: "ಈ ಡೆಮೊ ಚಿತ್ರದಲ್ಲಿ ಅಪಾಯಕಾರಿ ತ್ಯಾಜ್ಯ ಇರಬಹುದು. ಅದನ್ನು ಮುಚ್ಚಿ ಅಧಿಕೃತ ಸಂಗ್ರಹ ಕೇಂದ್ರಕ್ಕೆ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ. ಗ್ರೀನ್‌ಪಾಯಿಂಟ್‌ಗಳಿಗೆ ಮೊದಲು ಪುರಸಭೆ ಸಿಬ್ಬಂದಿ ಭೌತಿಕವಾಗಿ ಪರಿಶೀಲಿಸಬೇಕು.", text: "ಡೆಮೊ ಮೋಡ್‌ನಲ್ಲಿ ಕಸಮುಕ್ತಿ ಪ್ರದರ್ಶನ ಡೇಟಾದಿಂದ ಸುರಕ್ಷತಾ ಮಾರ್ಗದರ್ಶನ ನೀಡುತ್ತದೆ. ವಸ್ತು, ಸಂಗ್ರಹ ಮಾರ್ಗ ಅಥವಾ ಪರಿಶೀಲನೆಯ ಬಗ್ಗೆ ಕೇಳಿ." }
    }[language] || undefined;
    const answer = demoAnswers || {
      image: "This demo image shows a potentially hazardous waste item. Keep it sealed and take it to an authorised collection centre. A municipal worker must verify the physical deposit before any GreenPoints are awarded.",
      text: "In demo mode, KasaMukti provides safety guidance from the presentation dataset. Ask about a material, collection route, or the verification step."
    };
    return {
      answer: body.imageData ? answer.image : answer.text,
      confidence: 0.94,
      contextMetadata: { imageAnalyzed: Boolean(body.imageData), simulated: true },
      sources: [{ id: "DEMO-SAFETY-GUIDANCE" }]
    };
  }
  if (isDemoMode) return {};
  if (!apiBaseUrl) {
    throw new Error("Live API is not configured. Set VITE_API_BASE_URL in frontend/.env, or set VITE_DEMO_MODE=true for the clearly labelled presentation demo.");
  }
  const token = await accessToken();
  const versionedPath = import.meta.env.VITE_API_VERSIONED !== "false" ? `/api/v1${path}` : path;
  const response = await fetch(`${apiBaseUrl}${versionedPath}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(import.meta.env.VITE_DEMO_MODE === "true" ? { "X-Demo-Role": role, "X-Demo-User": userId } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : import.meta.env.VITE_COGNITO_ID_TOKEN ? { Authorization: `Bearer ${import.meta.env.VITE_COGNITO_ID_TOKEN}` } : {}),
      ...(options.headers || {})
    }
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) throw new Error("Your session has expired. Please sign in again.");
  if (response.status === 403) throw new Error(payload.error?.message || payload.error || "You are not authorized for this operation.");
  if (!response.ok || payload.success === false) throw new Error(payload.error?.message || payload.error || `AWS API returned ${response.status}`);
  return payload.success === true ? payload.data : payload;
}

export { apiBaseUrl as API_BASE };
