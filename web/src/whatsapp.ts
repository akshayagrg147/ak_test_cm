/**
 * WhatsApp click-to-chat only: builds a wa.me link that opens a chat on the user's own
 * device. ViaCRM never sends, receives or reads WhatsApp messages.
 */

/** wa.me wants digits only with the country code; Indian 10-digit numbers get 91. */
export function whatsappNumber(phone: string): string | null {
  let digits = (phone || "").replace(/\D/g, "").replace(/^0+/, "");
  // "+91 0 98765 43210": drop the trunk 0 written after the country code.
  if (digits.length === 13 && digits.startsWith("910"))
    digits = "91" + digits.slice(3);
  if (digits.length === 10) return "91" + digits;
  if (digits.length >= 11 && digits.length <= 15) return digits;
  return null;
}

const TITLES = /^(mr|mrs|ms|miss|dr|shri|sri|smt|kumari)\.?$/i;

/** The name to address someone by: the first word that isn't a title such as "Mr." or "Smt.". */
export function addressName(fullName: string): string {
  const words = fullName.trim().split(/\s+/).filter(Boolean);
  return words.find((w) => !TITLES.test(w)) || words[0] || "";
}

export function whatsappGreeting(
  leadName: string,
  company: string,
  userName: string,
) {
  const first = addressName(leadName);
  const sender = [company, "se", userName.trim()].filter(Boolean).join(" ");
  return `Namaste ${first} ji, ${sender}. Aapki property enquiry ke baare mein message kar rahe hain.`;
}

export function whatsappLink(phone: string, text: string): string | null {
  const number = whatsappNumber(phone);
  return number
    ? `https://wa.me/${number}?text=${encodeURIComponent(text)}`
    : null;
}
