import { useEffect, useRef, useState } from "react";

import { HELP_LINK_TEXT } from "./advice.js";
import HelpPage from "./HelpPage.jsx";
import { checkFrom, clearHistory, loadHistory, saveCheck } from "./history.js";
import HistoryTable from "./HistoryTable.jsx";
import PasteLinkForm from "./PasteLinkForm.jsx";
import PhishingCharts from "./PhishingCharts.jsx";
import { checkLink } from "./scan.js";

// The help page lives at #help, so it needs no server routes and the browser's
// Back button returns to the checker.
export const HELP_HASH = "#help";

function currentHash() {
  return typeof window === "undefined" ? "" : window.location.hash;
}

export default function App({ check = checkLink }) {
  const [hash, setHash] = useState(currentHash);
  // The checks saved in this browser, newest first, read once when the page opens.
  const [checks, setChecks] = useState(loadHistory);

  useEffect(() => {
    const onHashChange = () => setHash(currentHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const onHelp = hash === HELP_HASH;
  const wasOnHelp = useRef(false);

  // Each check with a result is saved in this browser only, never sent anywhere.
  function remember(reply) {
    const saved = checkFrom(reply);
    if (saved) {
      // Built from the list on the page, so a check the browser couldn't store isn't lost.
      setChecks(saveCheck(saved, { current: checks }));
    }
  }

  // Each page change moves focus to its heading, without stealing initial focus.
  useEffect(() => {
    if (onHelp) {
      document.getElementById("help-heading")?.focus();
    } else if (wasOnHelp.current) {
      document.getElementById("checker-heading")?.focus();
    }
    wasOnHelp.current = onHelp;
  }, [onHelp]);

  return (
    <main className="page">
      {/* The same header on every page, so the help link is always in the same place. */}
      <header className="site-header">
        <p className="logo">LinkGuard</p>
        <a className="text-link help-link" href={HELP_HASH} aria-current={onHelp ? "page" : undefined}>
          {HELP_LINK_TEXT}
        </a>
      </header>
      {onHelp && <HelpPage />}
      {/* Hidden rather than removed while the help page shows, so the pasted link,
          its result and its advice are still there when the user comes back. */}
      <div hidden={onHelp}>
        <h1 id="checker-heading" tabIndex={-1}>Is this link safe?</h1>
        <p className="lead">
          Paste a link from a text, email or message. We check it for you without opening it.
        </p>
        <PasteLinkForm check={check} onResult={remember} />
        <HistoryTable
          checks={checks}
          onClear={() => {
            clearHistory();
            setChecks([]);
          }}
        />
        <PhishingCharts />
      </div>
    </main>
  );
}
