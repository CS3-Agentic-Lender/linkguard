# Backlog inputs: practice, comparable tools, user advice, accessibility

Research for writing LinkGuard's product backlog. Gathered 2026-09-29 from primary sources only. Citations are inline as [n]; the list is in section 6. Anything marked **(unconfirmed)** could not be read at source (see notes in section 6).

No URL was submitted to any scanner, and no phishing or suspicious site was visited.

## 1. Summary

- **One ordered backlog, owned by one Product Owner.** The Scrum Guide calls the Product Backlog "an emergent, ordered list", "the single source of work". The Product Owner orders it and keeps it transparent. The Developers size the items [1].
- **Epics should be user outcomes, not components.** LG-1 to LG-4 (Data, ML, Backend, Frontend) are split by component. Wake's INVEST asks for stories that "slice vertically through the layers" [2], and Atlassian builds epics from end-user needs and splits them by persona or process step [10]. Better epics would be outcomes such as "Check a link", "Understand why", "Know what to do next" and "Report and give feedback". The component work then goes in as Tasks and Subtasks under those stories. (This is an inference from [2][10]. No source says "never group by component" in so many words.)
- **Every story passes INVEST, has acceptance criteria and fits in one sprint** [1][2][3]. Use Given/When/Then for behaviour [7] and a checklist for rules such as copy, contrast or response time [8]. Write the acceptance criteria before development starts [8].
- **Estimate in story points, as a team, with planning poker** on Cohn's scale 0, 1, 2, 3, 5, 8, 13, 20, 40, 100 [5][6]. Anything too big for one sprint gets split before Sprint Planning [1][3].
- **Prioritise with MoSCoW, with Musts at no more than 60% of effort** and about 20% as Coulds for contingency [13]. The DSDM test for a Must: "would you cancel the project without it?" [13].
- **Comparable tools all give a hedged verdict plus reasons.** Nobody claims certainty. ScamAdviser says its score is "not a verdict — it is a risk indicator" [21], and Get Safe Online says a site is "likely to be legitimate" [20]. LinkGuard's "safe" level needs the same caveat.
- **Features common to the comparable tools:** a verdict level; reasons or highlights; last-checked date; community reviews or votes; a way to report a site or dispute a rating; sharing; a browser extension [14]–[22]. VirusTotal makes every submission public and shares it with partners [18]. LinkGuard should state its own privacy stance on stored scan history.
- **Advice per risk level is consistent across agencies:** don't click; contact the organisation using details you find yourself; if you gave bank details, ring your bank now; report to the Gardaí [25]–[33][36][37].
- **Ireland has no public link checker from a government agency.** The Irish reporting routes are your bank, your local Garda station, your email provider's "report phishing" button and your mobile provider. ComReg now labels texts from unregistered senders "Likely Scam" [29][30]. The UK's 7726 and report@phishing.gov.uk are for UK users [33][35].
- **Accessibility needs its own stories, not polish at the end.** For older users the relevant WCAG 2.2 AA criteria are contrast 4.5:1, 200% text resize, reflow, 24×24 px targets, errors described in text with a fix suggested, colour never the only signal (important for the risk levels) and results announced as status messages [38]–[42].

## 2. Backlog practice

### Scrum Guide 2020 [1]

| Rule | What the guide says |
|---|---|
| What the backlog is | "An emergent, ordered list of what is needed to improve the product. It is the single source of work undertaken by the Scrum Team." |
| Product Goal | Lives in the Product Backlog. "The rest of the Product Backlog emerges to define 'what' will fulfill the Product Goal." |
| Refinement | "Breaking down and further defining Product Backlog items into smaller more precise items… add details, such as a description, order, and size." It is ongoing. |
| Ready | Items "that can be Done by the Scrum Team within one Sprint are deemed ready for selection in a Sprint Planning event." |
| Sizing | "The Developers who will be doing the work are responsible for the sizing." |
| Product Owner | "One person, not a committee." Develops and communicates the Product Goal, creates and communicates items, orders them, and keeps the backlog "transparent, visible and understood". May delegate the work but stays accountable. |
| Done | An Increment exists only once an item meets the Definition of Done. |

### Stories

- **Format (Cohn):** "As a [type of user], I [want/need] to [do something], so that [benefit]" [3][4]. An epic is just "a large user story", and a theme is a collection of related stories [4].
- **INVEST (Wake, 2003)** [2]:
  - **Independent:** can be scheduled in any order.
  - **Negotiable:** details are worked out together, not fixed as a contract.
  - **Valuable** to the user: "slice vertically through the layers" rather than one story per layer.
  - **Estimable.**
  - **Small.**
  - **Testable:** you "could write a test for it".
- **Tasks should be SMART (Wake)** [2]: Specific, Measurable (agreed "done"), Achievable, Relevant to the story, Time-boxed.
- **Size:** a story that can't be finished in a sprint is too large [3]. Atlassian splits anything estimated in "weeks" [10] and anything over about 16 hours or 20 points [9].

### Acceptance criteria

- **Given/When/Then** (Dan North, 2006): "Given some initial context (the givens), When an event occurs, Then ensure some outcomes" [7]. Use it for behaviour, for example "Given a URL with an IP-address host, when I check it, then I see High risk and the reason 'uses a number address instead of a name'".
- **Checklist or rule style** [8]: clear, concise, testable statements with a pass/fail result, quantified where possible, in plain language, and written before development starts.
- **Where they go:** Jira's Acceptance Criteria field or the description [8].

### Estimation [5][6][9]

- **Story points** measure relative effort, complexity and risk, not hours [9]. Don't use them to judge people or productivity [9].
- **Planning poker** [5]:
  1. The Product Owner reads out the item.
  2. The team discusses it.
  3. Everyone picks a card privately, then all reveal at once.
  4. The highest and lowest estimators explain their reasoning.
  5. Re-vote until the estimates converge.
- **Card scale:** 0, 1, 2, 3, 5, 8, 13, 20, 40, 100 [5]. Consecutive values grow by roughly the same proportion (Weber's law), and the wide gaps at the top avoid false precision [6].

### MoSCoW (DSDM) [13]

| Priority | Meaning |
|---|---|
| **Must** | The "Minimum Usable SubseT". The test: without it, would you cancel the project or stop the release? If a workaround exists, it is not a Must. |
| **Should** | Important but not vital. The product is still viable without it. |
| **Could** | Desirable, and the first to be dropped. This is the contingency pool, about 20% of effort. |
| **Won't have this time** | Explicitly out of scope for now. |

- Keep Musts at **no more than 60% of effort**.
- Prioritise at three levels: project, increment and timebox (sprint).

### Epics, stories, tasks and subtasks

- **Atlassian's hierarchy:** initiative → epic → story → task/subtask [10][11]. Epics are "few in number", span sprints, are built from customer and end-user needs, and can have several teams working on them [10][11].
- **Ways to split an epic** [10]: one story per user persona, or one story per step in the user's process.
- **For LinkGuard:** keep the component labels (`data`, `ml`, `backend`, `frontend`) as labels on tasks, as AGENTS.md already requires, and make the epics user-facing (inference; see Summary).

## 3. Comparable tools

Read only from each tool's own product or help pages. Nothing was submitted.

| Tool | Verdict shown | Reasons / detail | History | Reporting / disputes | Sharing / other | Source |
|---|---|---|---|---|---|---|
| **Google Safe Browsing site status** (Transparency Report) | Current status of a URL, site or domain | Threat type: malware, phishing ("social engineering") or unwanted software. A 2017 redesign moved it to "simpler, clearer results" and "easier-to-interpret language" for people arriving from a warning | Shows the most recent scan result. Unsafe sites are added "within minutes of detection" | Separate forms to report a phishing page or malware | Technical data (ASes) moved to a separate dashboard; site owners use Search Console | [14][15][16][17] |
| **VirusTotal** (URL) | Detection ratio: engines flagging the URL out of those that reviewed it (70+ scanners and blocklists) | Per-engine label: clean, malware, phishing, malicious, suspicious or spam. Content category and HTTP headers | Past analyses are stored, so a URL can be looked up without rescanning | Community votes (score weighted by voter reputation) and comments | **Submissions are shared with partners and the public community**, so they are not private | [18][19] |
| **Get Safe Online "Check a website"** (UK, with Cifas and ScamAdviser) | Hedged result: "likely to be legitimate" or "may not be safe to use" | Trust score from 40+ data sources, plus weekly reports from law enforcement, regulators and brands | Not stated | Not confirmed | Free, no sign-up, results in seconds | [20] **(unconfirmed: page returned 403; taken from Get Safe Online's own search listing)** |
| **ScamAdviser** | Trust score from 1 to 100, described as "not a verdict — it is a risk indicator" | "Positive and Negative Highlights": domain age, registration length, reviews (own, Trustpilot, SiteJabber, WOT), traffic rank, backlinks, WHOIS privacy | Score changes over time | User reviews, scam reports, and owner disputes with manual review | Share via social, messaging or copied link; app and browser extension | [21] |
| **Norton Safe Web** | Safe / Caution / Unsafe / Untested ("Untested" means not enough data, and Norton advises not visiting) | Threat categories: malware, spyware, "annoyance factors" | Not stated | Community reviews (on safeweb.norton.com; not confirmed on a Norton help page) | Browser extension blocks dangerous pages and adds ratings to Google search results (Chrome) | [22] |
| **Irish / UK government** | **No public link checker found** for Ireland (NCSC, Gardaí, ComReg) or the UK (NCSC) | n/a | n/a | UK: NCSC Suspicious Email Reporting Service (report@phishing.gov.uk), scam-website report form, texts to 7726. The NCSC says it acts on every report but cannot tell you the outcome. Ireland: report to the Gardaí and your bank (section 4) | ComReg labels texts from unregistered senders "Likely Scam" (from 3 Jul 2025) and blocks them (from 3 Oct 2025) | [30][31][33][34][35] |

**Story ideas from the table** (inference): hedged verdict wording; a reasons list; a "checked on" timestamp; a "report this link" route to the right authority; a "we got this wrong" feedback button (the equivalent of a dispute); a way to share the result; a clear privacy note about what is stored and who sees it (unlike VirusTotal, where submissions are public).

## 4. "What to do next" advice

Suggested plain-language lines, each traced to a source. Wording is ours; the substance is the source's.

### Every result, including Safe

- "Even if a link looks safe, don't enter passwords or bank details from a link in a message you weren't expecting. Go to the company's website or app yourself instead." [29][32][37]
- "Your bank will never text you a link or ask for your PIN or password." [27][28][32]

### Suspicious

- "Don't click the link, and don't reply." [25][29][37]
- "If you think the message might be real, contact the company using a phone number or website you find yourself. Don't use the details in the message." [25][28][29][32][37]
- "Watch for pressure: messages that rush you, frighten you, or pretend to be someone official are common scam tricks." [32][37]
- "Then delete the message." [25][37]

### High risk

- All of the Suspicious lines, plus:
- "Report it. Use your email provider's 'report phishing' or 'junk' button. If someone keeps texting or calling you, ask your mobile provider to block the number." [23][29] ([23] unconfirmed)
- "In the UK, you can forward scam emails to report@phishing.gov.uk and scam texts to 7726." [33][35]

### If you already clicked, or typed in details

- **Bank or card details:** "Ring your bank straight away, using the number on the back of your card." [27][28][36]
- **Password:** "Change that password, and any other account where you used the same password." [36]
- **Opened a link or installed something:** "Run a full scan with your antivirus." [36] NCSC Ireland's guide goes further: if you clicked a link or installed an app on your phone, factory-reset the device (you'll lose data without a backup) and contact your mobile provider [24] **(unconfirmed: search excerpt only; this is heavy advice, so check with the source before showing it)**.
- **Lost money or gave details:** "Report it to your local Garda station. Bring copies of the messages, account details and any screenshots." [25][26][27]
- **Work device:** "Tell your IT department." [36]

### Irish reporting routes

| Situation | Where to report | Source |
|---|---|---|
| Money taken or bank details shared | Your bank, immediately (number on the card or the bank's website) | [27][28] |
| Any phishing, smishing or vishing, attempted or successful | Your local Garda station. The Garda "Online Declaration" only covers theft up to €500 and doesn't cover this | [23][25][26][27] |
| Scam happened on a website or marketplace | That site's own reporting tool, as well as the Gardaí | [26] |
| Scam email | Your email provider's "report phishing" feature | [23] (unconfirmed) |
| Persistent scam calls or texts | Your mobile provider (ask them to block the number) | [29] |
| An organisation facing a cyber incident | NCSC Ireland (info@ncsc.gov.ie) | [23] (unconfirmed) |
| Phishing page (anyone) | Google Safe Browsing report form | [17] |

**Not confirmed:** an Irish equivalent of the UK's 7726 text-forwarding code. No Irish source found says to forward scam texts to a short code.

## 5. Accessibility points (WCAG 2.2)

WCAG 2.2 became a W3C Recommendation on 5 October 2023 [39]. The criteria most relevant to older and less confident users on a paste-a-link page are:

| SC | Level | Requirement (short) | Why it matters for LinkGuard |
|---|---|---|---|
| [1.4.1 Use of Color](https://www.w3.org/TR/WCAG22/#use-of-color) | A | Colour is not the only way information is conveyed | The risk level needs a text label and an icon, not just green, amber or red |
| [1.4.3 Contrast (Minimum)](https://www.w3.org/TR/WCAG22/#contrast-minimum) | AA | Text contrast at least 4.5:1 (3:1 for large text) | Reduced contrast sensitivity in older users [42] |
| [1.4.4 Resize Text](https://www.w3.org/TR/WCAG22/#resize-text) | AA | Text resizes to 200% with nothing lost | |
| [1.4.10 Reflow](https://www.w3.org/TR/WCAG22/#reflow) | AA | No two-way scrolling at narrow width or high zoom | Many users will paste from a phone |
| [1.4.11 Non-text Contrast](https://www.w3.org/TR/WCAG22/#non-text-contrast) | AA | UI parts and graphics at least 3:1 | Input border, check button, risk icon |
| [2.4.7 Focus Visible](https://www.w3.org/TR/WCAG22/#focus-visible) / [2.4.11 Focus Not Obscured](https://www.w3.org/TR/WCAG22/#focus-not-obscured-minimum) (new in 2.2) | AA | Keyboard focus is visible and not hidden | |
| [2.5.8 Target Size (Minimum)](https://www.w3.org/TR/WCAG22/#target-size-minimum) (new in 2.2) | AA | Targets at least 24×24 CSS px, or spaced out | Reduced dexterity [42] |
| [3.2.6 Consistent Help](https://www.w3.org/TR/WCAG22/#consistent-help) (new in 2.2) | A | Help sits in the same place on every page | A "Where to get help" link |
| [3.3.1 Error Identification](https://www.w3.org/TR/WCAG22/#error-identification) | A | Errors are identified and described in text | "That doesn't look like a web address", not just a red border |
| [3.3.2 Labels or Instructions](https://www.w3.org/TR/WCAG22/#labels-or-instructions) | A | Inputs have labels or instructions | "Paste the link here" |
| [3.3.3 Error Suggestion](https://www.w3.org/TR/WCAG22/#error-suggestion) | AA | Suggest how to fix the error | |
| [4.1.3 Status Messages](https://www.w3.org/TR/WCAG22/#status-messages) | AA | Status messages are announced without moving focus | Screen readers announce the result when it appears [41] |
| [3.1.5 Reading Level](https://www.w3.org/TR/WCAG22/#reading-level) | AAA | Text needing more than lower-secondary reading level has a simpler version | Stretch goal for the reasons and advice text [40] |

The W3C's page on older users lists declining vision (contrast, colour, near focus), dexterity (small targets), hearing, and cognition (short-term memory, concentration) [42].

## 6. Sources

Accessed 2026-09-29.

1. Schwaber & Sutherland, *The Scrum Guide* (2020). https://scrumguides.org/scrum-guide.html
2. Bill Wake, "INVEST in Good Stories, and SMART Tasks" (2003). https://xp123.com/invest-in-good-stories-and-smart-tasks/
3. Mountain Goat Software (Mike Cohn), "User Stories". https://www.mountaingoatsoftware.com/agile/user-stories
4. Mike Cohn, "Stories, Epics and Themes". https://www.mountaingoatsoftware.com/blog/stories-epics-and-themes
5. Mountain Goat Software, "Planning Poker". https://www.mountaingoatsoftware.com/agile/planning-poker
6. Mike Cohn, "Why the Fibonacci Sequence Works Well for Estimating". https://www.mountaingoatsoftware.com/blog/why-the-fibonacci-sequence-works-well-for-estimating
7. Dan North, "Introducing BDD" (Better Software, 2006). https://dannorth.net/blog/introducing-bdd/
8. Atlassian, "Acceptance criteria". https://www.atlassian.com/work-management/project-management/acceptance-criteria
9. Atlassian, "Story points and estimation". https://www.atlassian.com/agile/project-management/estimation
10. Atlassian, "Agile epics". https://www.atlassian.com/agile/project-management/epics
11. Atlassian, "Epics, stories, and initiatives". https://www.atlassian.com/agile/project-management/epics-stories-themes
12. Atlassian, "Product backlog". https://www.atlassian.com/agile/scrum/backlogs
13. Agile Business Consortium, *DSDM Project Framework Handbook*, ch. 10 "MoSCoW Prioritisation". https://www.agilebusiness.org/dsdm-project-framework/moscow-prioritisation.html
14. Google Transparency Report, "Safe Browsing site status". https://transparencyreport.google.com/safe-browsing/search (tool page; description via [15][16])
15. Google Search Central Blog, "Updates to the Google Safe Browsing's Site Status Tool" (Mar 2017). https://developers.google.com/search/blog/2017/03/updates-to-google-safe-browsings-site
16. Google, "Safe Browsing FAQs", Transparency Report Help. https://support.google.com/transparencyreport/answer/7380435?hl=en
17. Google Safe Browsing, "Report a phishing page". https://safebrowsing.google.com/safebrowsing/report_phish/ (form not used; existence confirmed via search)
18. VirusTotal docs, "How it works". https://docs.virustotal.com/docs/how-it-works
19. VirusTotal docs, "Reports". https://docs.virustotal.com/docs/results-reports
20. Get Safe Online, "Check a website". https://www.getsafeonline.org/checkawebsite/ (**403 / bot wall; details from Get Safe Online's own search listings only**)
21. ScamAdviser, "ScamAdviser Trust Score Explained". https://www.scamadviser.com/articles/scamadviser-algorithm-explainer
22. Norton Support, "Browse the Internet securely with Norton Safe Web". https://support.norton.com/sp/en/us/home/current/solutions/v19116982
23. NCSC Ireland, "Phishing". https://www.ncsc.gov.ie/phishing/ (**connection refused on 2026-09-29; content from search excerpts only**)
24. NCSC Ireland, "Quick Guide: Phishing" (PDF). https://www.ncsc.gov.ie/pdfs/NCSC_Quick_Guide_Phishing.pdf (**unreachable; search excerpts only**)
25. An Garda Síochána, "Phishing Attacks". https://www.garda.ie/en/crime/cyber-crime/phishing-attacks.html
26. An Garda Síochána, "I've been caught out by an online scam. What should I do?". https://www.garda.ie/en/crime/cyber-crime/i-ve-been-caught-out-by-an-online-scam-what-should-i-do-.html
27. An Garda Síochána, "Fraud". https://www.garda.ie/en/crime/fraud/
28. FraudSMART (Banking & Payments Federation Ireland), "Smishing". https://www.fraudsmart.ie/personal/fraud-scams/text-scams/smishing/
29. ComReg, "Scam Calls & Texts". https://www.comreg.ie/advice-information/scam-calls/
30. ComReg, "From 3 July 2025, unregistered SMS Sender IDs to be modified to 'Likely Scam'". https://www.comreg.ie/from-3-july-2025-unregistered-sms-sender-ids-to-be-modified-to-likely-scam/
31. UK NCSC, "Phishing scams: how to spot and report them". https://www.ncsc.gov.uk/collection/phishing-scams
32. UK NCSC, "How to spot a scam email, text message or call". https://www.ncsc.gov.uk/collection/phishing-scams/spot-scams
33. UK NCSC, "Report a scam email". https://www.ncsc.gov.uk/collection/phishing-scams/report-scam-email
34. UK NCSC, "Report a scam website". https://www.ncsc.gov.uk/collection/phishing-scams/report-scam-website
35. UK NCSC, "Report a scam text". https://www.ncsc.gov.uk/collection/phishing-scams/report-scam-text-message (7726 detail from NCSC search excerpt; page not fetched)
36. UK NCSC, "If you've shared sensitive information". https://www.ncsc.gov.uk/collection/phishing-scams/what-to-do
37. CISA, "Recognize and Report Phishing". https://www.cisa.gov/secure-our-world/recognize-and-report-phishing
38. W3C, *Web Content Accessibility Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/
39. W3C WAI, "What's New in WCAG 2.2". https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
40. W3C WAI, "Understanding SC 3.1.5 Reading Level". https://www.w3.org/WAI/WCAG22/Understanding/reading-level.html
41. W3C WAI, "Understanding SC 4.1.3 Status Messages". https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
42. W3C WAI, "Older Users and Web Accessibility". https://www.w3.org/WAI/older-users/
