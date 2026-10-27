// Checks every colour pair LinkGuard uses against the WCAG 2.2 contrast minimums,
// reading the colours from src/styles/tokens.css so the check can't drift from them.
// Prints a table and exits with 1 if any pair fails.
//
//   node frontend/scripts/check-contrast.mjs

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const TEXT = 4.5; // WCAG 1.4.3, normal-size text
const NON_TEXT = 3; // WCAG 1.4.11, icons, borders and the focus outline

// [foreground, background, minimum, what it is]
const PAIRS = [
  ["text", "background", TEXT, "Body text on the page"],
  ["text", "surface", TEXT, "Body text on a card"],
  ["text-muted", "background", TEXT, "Helper text on the page"],
  ["text-muted", "surface", TEXT, "Helper text on a card"],
  ["on-primary", "primary", TEXT, "Check button label"],
  ["on-primary", "primary-hover", TEXT, "Check button label, hovered"],
  ["primary", "surface", TEXT, "Link text on a card"],
  ["error", "surface", TEXT, "Error message next to the link box"],
  ["error", "error-surface", TEXT, "Error message on its own surface"],
  ["risk-safe", "risk-safe-surface", TEXT, "Safe word and icon"],
  ["risk-suspicious", "risk-suspicious-surface", TEXT, "Suspicious word and icon"],
  ["risk-high", "risk-high-surface", TEXT, "High risk word and icon"],
  ["risk-safe", "surface", TEXT, "Safe word on a card"],
  ["risk-suspicious", "surface", TEXT, "Suspicious word on a card"],
  ["risk-high", "surface", TEXT, "High risk word on a card"],
  ["border", "surface", NON_TEXT, "Link box border"],
  ["border", "background", NON_TEXT, "Link box border on the page"],
  ["focus", "surface", NON_TEXT, "Focus outline on a card"],
  ["focus", "background", NON_TEXT, "Focus outline on the page"],
  ["focus", "primary", NON_TEXT, "Focus outline next to the button"],
];

export function readColours(css) {
  const colours = {};
  for (const [, name, hex] of css.matchAll(/--color-([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    colours[name] = hex;
  }
  return colours;
}

function luminance(hex) {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

const tokensPath = fileURLToPath(new URL("../src/styles/tokens.css", import.meta.url));
const colours = readColours(readFileSync(tokensPath, "utf8"));

let failures = 0;
const rows = PAIRS.map(([fg, bg, minimum, what]) => {
  if (!colours[fg] || !colours[bg]) {
    throw new Error(`Missing colour token: --color-${colours[fg] ? bg : fg}`);
  }
  const ratio = contrast(colours[fg], colours[bg]);
  const passes = ratio >= minimum;
  if (!passes) failures += 1;
  return {
    "What": what,
    "Foreground": `${fg} ${colours[fg]}`,
    "Background": `${bg} ${colours[bg]}`,
    "Ratio": `${ratio.toFixed(2)}:1`,
    "Needs": `${minimum}:1`,
    "Result": passes ? "pass" : "FAIL",
  };
});

console.table(rows);
console.log(failures ? `${failures} of ${rows.length} pairs fail.` : `All ${rows.length} pairs pass.`);
process.exitCode = failures ? 1 : 0;
