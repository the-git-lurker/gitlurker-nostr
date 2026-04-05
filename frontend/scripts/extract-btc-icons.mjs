import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const esm = path.join(
  __dirname,
  "../node_modules/@bitcoin-design/bitcoin-icons-svg/outline/esm",
);
const names = [
  "StarIcon",
  "ShareIcon",
  "MessageIcon",
  "BitcoinIcon",
  "LightningIcon",
  "NoDollarsIcon",
  "MagicWandIcon",
  "QuestionIcon",
  "QuestionCircleIcon",
  "DevicesIcon",
  "LinuxTerminalIcon",
  "ExchangeIcon",
  "LinkIcon",
  "NodeIcon",
  "WalletIcon",
  "ProxyIcon",
  "CreditCardIcon",
  "FileIcon",
  "CodeIcon",
  "RelayIcon",
  "KeyIcon",
  "GraphIcon",
  "GlobeIcon",
  "GearIcon",
  "InfoCircleIcon",
  "MoonIcon",
  "SunIcon",
  "SofaIcon",
];
const out = {};
for (const n of names) {
  const s = fs.readFileSync(path.join(esm, `${n}.js`), "utf8");
  const m = s.match(/svg: `([\s\S]*?)`/);
  if (m) out[n] = m[1];
  else console.error("missing", n);
}
const dest = path.join(__dirname, "../src/js/btcOutlineSvgs.generated.js");
const body = `/* Auto-generated from @bitcoin-design/bitcoin-icons-svg outline (MIT). Run: node scripts/extract-btc-icons.mjs */
/** @type {Record<string, string>} */
export const BTC_OUTLINE_SVGS = ${JSON.stringify(out, null, 2)};
`;
fs.writeFileSync(dest, body, "utf8");
console.error("Wrote", dest);
