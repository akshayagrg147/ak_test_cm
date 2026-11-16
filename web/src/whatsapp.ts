/**
 * WhatsApp click-to-chat only: builds a wa.me link that opens a chat on the user's own
 * device. ViaCRM never sends, receives or reads WhatsApp messages.
 */

/** wa.me wants digits only with the country code; Indian 10-digit numbers get 91. */
export function whatsappNumber(phone: string): string | null {
  const digits = (phone || "").replace(/\D/g, "").replace(/^0+/, "");
  if (digits.length === 10) return "91" + digits;
  if (digits.length >= 11 && digits.length <= 15) return digits;
  return null;
}

export function whatsappGreeting(
  leadName: string,
  company: string,
  userName: string,
) {
  const first = leadName.trim().split(/\s+/)[0] || leadName.trim();
  return `Namaste ${first} ji, ${company} se ${userName}. Aapki property enquiry ke baare mein message kar rahe hain.`;
}

export function whatsappLink(phone: string, text: string): string | null {
  const number = whatsappNumber(phone);
  return number
    ? `https://wa.me/${number}?text=${encodeURIComponent(text)}`
    : null;
}
