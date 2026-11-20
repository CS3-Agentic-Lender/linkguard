// Every line of advice the app shows, copied word for word from docs/advice.md,
// which lists at least one official source for each. Change both together:
// advice.test.jsx fails if a line here is missing from that file.

// Shown with every result, including Safe.
export const EVERY_RESULT = [
  "Don't enter passwords or bank details from a link in a message you weren't expecting. Go to the company's website or app yourself instead.",
  "Your bank will never ask for your PIN or your full password in a text, an email or a phone call.",
];

export const SUSPICIOUS = [
  "Don't click the link and don't reply.",
  "If the message might be real, contact the company using a phone number or website you find yourself.",
  "Watch for pressure: messages that rush you, frighten you or pretend to be someone official.",
  "Then delete the message.",
];

// High risk shows all the Suspicious lines, plus these.
export const HIGH_RISK_EXTRA = [
  "Report the message at your local Garda station.",
  "If a number keeps texting or calling you, ask your mobile provider to block it.",
];

// Each risk level's own advice, keyed by the class the result card uses.
export const LEVEL_ADVICE = {
  safe: [],
  suspicious: SUSPICIOUS,
  high: [...SUSPICIOUS, ...HIGH_RISK_EXTRA],
};

// Shown under every result.
export const ALREADY_CLICKED_HEADING = "If you already clicked";
export const ALREADY_CLICKED = [
  { situation: "You gave bank or card details", line: "Ring your bank straight away, using the number on the back of your card." },
  { situation: "You typed a password", line: "Change it, and change it on any other account that uses the same password." },
  { situation: "You opened a link or installed something", line: "Run a full antivirus scan." },
  { situation: "You lost money or gave details", line: "Report it to your local Garda station, and bring copies of the messages." },
  { situation: "It was on a work device", line: "Tell your IT department." },
];

// The help page: the Irish reporting routes.
export const HELP_LINK_TEXT = "Where to get help";
export const HELP_ROUTES = [
  {
    situation: "Money was taken, or you shared bank details", where: "Your bank, straight away",
    source: { name: "FraudSMART: Smishing", url: "https://www.fraudsmart.ie/personal/fraud-scams/text-scams/smishing/" },
  },
  {
    situation: "Any scam email, text or call, whether it worked or not", where: "Your local Garda station",
    source: { name: "NCSC Ireland: Phishing guide", url: "https://www.ncsc.gov.ie/pdfs/NCSC_Quick_Guide_Phishing.pdf" },
  },
  {
    situation: "The scam happened on a website or marketplace",
    where: "That website's own reporting tool, as well as the Gardaí",
    source: { name: "Garda: Online scam advice", url: "https://www.garda.ie/en/crime/cyber-crime/i-ve-been-caught-out-by-an-online-scam-what-should-i-do-.html" },
  },
  {
    situation: "A scam email", where: "Your email provider's \"report phishing\" option, if it has one",
    source: { name: "NCSC Ireland: Phishing guide", url: "https://www.ncsc.gov.ie/pdfs/NCSC_Quick_Guide_Phishing.pdf" },
  },
  {
    situation: "Scam calls or texts that keep coming", where: "Your mobile provider. Ask them to block the number",
    source: { name: "ComReg: Scam calls and texts", url: "https://www.comreg.ie/advice-information/scam-calls/" },
  },
];
